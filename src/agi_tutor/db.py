import os, sqlite3, pathlib
DB_DIR = os.getenv('DB_DIR', '/var/data')
pathlib.Path(DB_DIR).mkdir(parents=True, exist_ok=True)
DB_PATH = os.getenv('DB_PATH', os.path.join(DB_DIR, 'agi_tutor.sqlite'))

def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

import sqlite3
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

from .config import settings

def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    Path(settings.db_path).touch(exist_ok=True)
    with get_conn() as c:
        c.executescript("""
        PRAGMA journal_mode=WAL;

        CREATE TABLE IF NOT EXISTS users(
          id INTEGER PRIMARY KEY,
          name TEXT NOT NULL,
          stage TEXT NOT NULL,
          region TEXT NOT NULL,
          sessions_per_week INTEGER NOT NULL,
          hours_per_session REAL NOT NULL,
          school_year_end TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS plans(
          id INTEGER PRIMARY KEY,
          user_id INTEGER NOT NULL,
          curriculum_path TEXT NOT NULL,
          generated_on TEXT NOT NULL,
          total_sessions INTEGER NOT NULL,
          plan_json TEXT NOT NULL,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS sessions(
          id INTEGER PRIMARY KEY,
          user_id INTEGER NOT NULL,
          topic TEXT NOT NULL,
          started_at TEXT NOT NULL,
          ended_at TEXT,
          transcript TEXT DEFAULT '',
          mastery_estimate REAL DEFAULT 0.0,
          confidence REAL DEFAULT 0.0,
          FOREIGN KEY(user_id) REFERENCES users(id)
        );

        CREATE TABLE IF NOT EXISTS progress(
          id INTEGER PRIMARY KEY,
          user_id INTEGER NOT NULL,
          topic TEXT NOT NULL,
          mastery REAL NOT NULL,
          updated_at TEXT NOT NULL,
          UNIQUE(user_id, topic),
          FOREIGN KEY(user_id) REFERENCES users(id)
        );
        """)
        c.commit()

def fetchone(query: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    with get_conn() as c:
        cur = c.execute(query, tuple(params))
        return cur.fetchone()

def fetchall(query: str, params: Iterable[Any] = ()) -> list[sqlite3.Row]:
    with get_conn() as c:
        cur = c.execute(query, tuple(params))
        return cur.fetchall()

def execute(query: str, params: Iterable[Any] = ()) -> int:
    with get_conn() as c:
        cur = c.execute(query, tuple(params))
        c.commit()
        return cur.lastrowid

def executemany(query: str, rows: Iterable[Iterable[Any]]) -> None:
    with get_conn() as c:
        c.executemany(query, rows)
        c.commit()
