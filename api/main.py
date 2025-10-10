from __future__ import annotations
from datetime import date, datetime
from typing import List, Optional
import sqlite3
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from agi_tutor.module_planner import make_plan

DB = "tutor.db"
app = FastAPI(title="AGI Tutor API")

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

# ---------- models ----------
class Signup(BaseModel):
    name: str
    region: str
    stage: str
    hours_per_session: float = 1.0
    sessions_per_week: int = 2
    school_year_end: str  # YYYY-MM-DD

class PlanRequest(BaseModel):
    user_id: int
    subject_code: str  # maths, english
    hours_per_week: float
    start_date: str    # YYYY-MM-DD
    end_date: str      # YYYY-MM-DD

class StartSession(BaseModel):
    user_id: int
    module_id: int

# ---------- endpoints ----------
@app.post("/signup")
def signup(s: Signup):
    con = db()
    cur = con.cursor()
    # insert or update
    cur.execute("""
    INSERT INTO users(name, region, stage, sessions_per_week, hours_per_session, school_year_end)
    VALUES(?,?,?,?,?,?)
    """, (s.name, s.region, s.stage, s.sessions_per_week, s.hours_per_session, s.school_year_end))
    con.commit()
    uid = cur.lastrowid
    con.close()
    return {"user_id": uid}

@app.post("/plan")
def create_plan(p: PlanRequest):
    # build plan via module planner
    start = date.fromisoformat(p.start_date)
    end = date.fromisoformat(p.end_date)
    # look up user for region and year
    con = db()
    u = con.execute("SELECT * FROM users WHERE id=?", (p.user_id,)).fetchone()
    if not u:
        con.close()
        raise HTTPException(404, "User not found")

    payload = make_plan(u["name"], u["region"], u["stage"], p.subject_code, p.hours_per_week, start, end)
    cur = con.cursor()
    cur.execute("""INSERT INTO plans(user_id, subject_code, start_date, end_date, hours_per_week, created_at)
                   VALUES(?,?,?,?,?,?)""",
                (p.user_id, p.subject_code, p.start_date, p.end_date, p.hours_per_week,
                 datetime.utcnow().isoformat(timespec="seconds")))
    plan_id = cur.lastrowid

    order_idx = 0
    for m in payload["modules"]:
        cur.execute("""INSERT INTO modules(plan_id, title, summary, est_minutes, order_index)
                       VALUES(?,?,?,?,?)""",
                    (plan_id, m["title"], m.get("summary",""), int(m["est_minutes"]), order_idx))
        mid = cur.lastrowid
        for j, item in enumerate(m.get("items", [])):
            cur.execute("""INSERT INTO module_items(module_id, objective, success_criteria, order_index)
                           VALUES(?,?,?,?)""",
                        (mid, item["objective"], item.get("success_criteria",""), j))
        order_idx += 1

    con.commit()
    con.close()
    return {"plan_id": plan_id}

@app.get("/modules")
def list_modules(user_id: int, subject_code: str):
    con = db()
    plan = con.execute("""SELECT id FROM plans
                          WHERE user_id=? AND subject_code=?
                          ORDER BY created_at DESC LIMIT 1""", (user_id, subject_code)).fetchone()
    if not plan:
        con.close()
        return {"modules": []}
    rows = con.execute("""SELECT m.id, m.title, m.summary, m.est_minutes, m.order_index
                          FROM modules m WHERE m.plan_id=? ORDER BY m.order_index""", (plan["id"],)).fetchall()
    out = []
    for r in rows:
        items = con.execute("""SELECT objective, success_criteria, order_index
                               FROM module_items WHERE module_id=? ORDER BY order_index""", (r["id"],)).fetchall()
        out.append({
            "id": r["id"],
            "title": r["title"],
            "summary": r["summary"],
            "est_minutes": r["est_minutes"],
            "items": [dict(i) for i in items],
        })
    con.close()
    return {"modules": out}

@app.post("/session/start")
def session_start(s: StartSession):
    con = db()
    mod = con.execute("SELECT * FROM modules WHERE id=?", (s.module_id,)).fetchone()
    if not mod:
        con.close()
        raise HTTPException(404, "Module not found")
    items = con.execute("""SELECT objective, success_criteria, order_index
                           FROM module_items WHERE module_id=? ORDER BY order_index""", (s.module_id,)).fetchall()
    con.close()
    # Return the module payload the UI should pass into your tutor’s system prompt
    return {
        "module": {
            "title": mod["title"],
            "summary": mod["summary"],
            "est_minutes": mod["est_minutes"],
            "items": [dict(i) for i in items]
        }
    }

# --- Health + Root routes for Render ---
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
def root():
    return {"ok": True, "service": "agi-tutor-api"}

@router.get("/health")
def health():
    return {"status": "ok"}

app.include_router(router)

# --- direct routes for Render health checks ---
@app.get("/", include_in_schema=True)
def _root2():
    return {"ok": True, "service": "agi-tutor-api"}

@app.get("/health", include_in_schema=True)
def _health2():
    return {"status": "ok"}

# ---------- schema init ----------
def init_db():
    con = db()
    cur = con.cursor()
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS users(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        region TEXT NOT NULL,
        stage TEXT NOT NULL,
        sessions_per_week INTEGER NOT NULL,
        hours_per_session REAL NOT NULL,
        school_year_end TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS plans(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        subject_code TEXT NOT NULL,
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        hours_per_week REAL NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS modules(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        est_minutes INTEGER NOT NULL,
        order_index INTEGER NOT NULL
    );

    CREATE TABLE IF NOT EXISTS module_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        objective TEXT NOT NULL,
        success_criteria TEXT,
        order_index INTEGER NOT NULL
    );
    """)
    con.commit()
    con.close()

@app.on_event("startup")
def _startup_init():
    init_db()

@app.get("/debug/tables")
def _tables():
    con = db()
    rows = con.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name").fetchall()
    con.close()
    return {"tables": [r["name"] for r in rows]}


# --- one-off lite migration for Render DB ---
def _col_exists(con, table: str, col: str) -> bool:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r["name"] == col for r in rows)

@app.post("/admin/migrate-lite")
def migrate_lite():
    con = db()
    cur = con.cursor()

    # add missing plan columns (no-op if they already exist)
    if not _col_exists(con, "plans", "subject_code"):
        cur.execute("ALTER TABLE plans ADD COLUMN subject_code TEXT")
    if not _col_exists(con, "plans", "hours_per_week"):
        cur.execute("ALTER TABLE plans ADD COLUMN hours_per_week REAL")
    if not _col_exists(con, "plans", "created_at"):
        cur.execute("ALTER TABLE plans ADD COLUMN created_at TEXT")

    # create module tables if missing (matches init_db schema)
    cur.executescript("""
    CREATE TABLE IF NOT EXISTS modules(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        plan_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        summary TEXT,
        est_minutes INTEGER NOT NULL,
        order_index INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS module_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        module_id INTEGER NOT NULL,
        objective TEXT NOT NULL,
        success_criteria TEXT,
        order_index INTEGER NOT NULL
    );
    """)

    con.commit()

    # return current plans columns for proof
    cols = [r["name"] for r in con.execute("PRAGMA table_info(plans)").fetchall()]
    con.close()
    return {"ok": True, "plans_columns": cols}

# temporary reset route
@app.post("/admin/reset-db")
def admin_reset_db():
    from agi_tutor.reset_db import reset
    reset()
    return {"ok": True, "note": "DB reset"}
