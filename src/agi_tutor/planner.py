from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime
from typing import Dict, Any, List
import json
from .curriculum import to_plan_items
from .db import execute, fetchone
from .config import settings

@dataclass
class Signup:
    name: str
    stage: str
    region: str
    sessions_per_week: int
    hours_per_session: float
    school_year_end: date

def weeks_remaining(today: date, end: date) -> int:
    days = (end - today).days
    return max(0, (days + 6) // 7)

def generate_plan(user_id: int, curr: Curriculum, sessions_per_week: int, end_date: date) -> dict:
    w_rem = weeks_remaining(date.today(), end_date)
    total_sessions = w_rem * sessions_per_week
    items = to_plan_items(curr)
    # naive ordering, prerequisites already baked into the file order
    plan = {"generated_on": date.today().isoformat(),
            "subject": curr.subject,
            "total_sessions": total_sessions,
            "items": items}
    execute(
        "INSERT INTO plans(user_id, curriculum_path, generated_on, total_sessions, plan_json) VALUES(?,?,?,?,?)",
        (user_id, f"data/{curr.stage}_{curr.region}_{curr.subject}.json",
         plan["generated_on"], total_sessions, json.dumps(plan)),
    )
    return plan

def next_topic_for(user_id: int) -> str | None:
    row = fetchone("SELECT plan_json FROM plans WHERE user_id=? ORDER BY id DESC LIMIT 1", (user_id,))
    if not row:
        return None
    import json
    plan = json.loads(row["plan_json"])
    items: List[dict[str, Any]] = plan["items"]
    # pick first topic not mastered to at least 0.8
    from .db import fetchone as f1
    for item in items:
        p = f1("SELECT mastery FROM progress WHERE user_id=? AND topic=?", (user_id, item["topic"]))
        if not p or p["mastery"] < 0.8:
            return item["topic"]
    return None
