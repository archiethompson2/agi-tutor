from __future__ import annotations
import argparse
import json
from datetime import date
from pathlib import Path
from typing import Any, Dict

from .config import settings
from .db import init_db, execute, fetchone
from .curriculum import load_curriculum
from .planner import generate_plan
from .session_manager import run_session

def main() -> None:
    p = argparse.ArgumentParser(prog="agi-tutor")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init-db")

    add = sub.add_parser("add-user")
    add.add_argument("--name", required=True)
    add.add_argument("--stage", required=True, help="e.g. Year8-Maths")
    add.add_argument("--region", required=True, help="e.g. Wales")
    add.add_argument("--sessions-per-week", type=int, required=True)
    add.add_argument("--hours-per-session", type=float, required=True)
    add.add_argument("--school-year-end", required=True, help="YYYY-MM-DD")

    gp = sub.add_parser("generate-plan")
    gp.add_argument("--user-name", required=True)
    gp.add_argument("--curriculum-path", default="data/Year8_Wales_Maths.json")

    ss = sub.add_parser("start-session")
    ss.add_argument("--user-name", required=True)
    ss.add_argument("--topic", help="optional override")

    args = p.parse_args()

    if args.cmd == "init-db":
        init_db()
        print(f"DB ready at {settings.db_path}")
        return

    if args.cmd == "add-user":
        uid = execute(
            "INSERT INTO users(name, stage, region, sessions_per_week, hours_per_session, school_year_end) VALUES(?,?,?,?,?,?)",
            (args.name, args.stage, args.region, args.sessions_per_week, args.hours_per_session, args.school_year_end)
        )
        print(f"User created with id {uid}")
        return

    if args.cmd == "generate-plan":
        u = fetchone("SELECT * FROM users WHERE name=?", (args.user_name,))
        assert u, "User not found"
        curr = load_curriculum(args.curriculum_path)
        plan = generate_plan(u["id"], curr, u["sessions_per_week"], date.fromisoformat(u["school_year_end"]))
        print(json.dumps(plan, indent=2))
        return

    if args.cmd == "start-session":
        u = fetchone("SELECT * FROM users WHERE name=?", (args.user_name,))
        assert u, "User not found"
        # build runtime context
        context: Dict[str, Any] = {
            "student": {"name": u["name"], "stage": u["stage"], "region": u["region"]},
            "time": {
                "sessions_per_week": u["sessions_per_week"],
                "hours_per_session": u["hours_per_session"],
                "school_year_end": u["school_year_end"],
            },
        }
        if args.topic:
            context["curriculum_topic"] = args.topic
        run_session(u["id"], u["name"], context)
        return

if __name__ == "__main__":
    main()
