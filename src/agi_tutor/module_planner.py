from __future__ import annotations
from datetime import date, timedelta
from typing import Any, List
import math
import json
import os

from agi_tutor.curriculum import load_curriculum
from agi_tutor.agi_agent import call_model

SYSTEM = (
    "You plan learning modules for a school curriculum. "
    "Group objectives into ordered modules of 30 to 60 minutes each, "
    "respect prerequisite dependencies and the available total hours. "
    "Return strict JSON with fields modules:[{title, summary, est_minutes, items:[{objective, success_criteria}]}]."
)

def weeks_between(start: date, end: date) -> int:
    return max(1, ((end - start).days + 6) // 7)

def make_plan(name: str, region: str, year: str, subject: str,
              hours_per_week: float, start: date, end: date) -> dict[str, Any]:
    spec = load_curriculum(region, year, subject)
    weeks = weeks_between(start, end)
    total_minutes = int(hours_per_week * 60 * weeks)

    user = {
        "student": {"name": name, "region": region, "year": year},
        "subject": subject,
        "timebox": {"weeks": weeks, "hours_per_week": hours_per_week, "total_minutes": total_minutes},
        "objectives": spec["objectives"]
    }

    messages = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": json.dumps(user)}
    ]
    out = call_model(messages)
    # Try to parse model response
    try:
        start = out.find("{")
        endi = out.rfind("}")
        payload = json.loads(out[start:endi+1])
        return payload
    except Exception:
        # Fallback simple split if the model output is not parseable
        objs = spec["objectives"]
        per = max(1, math.ceil(len(objs) / max(1, weeks)))
        modules = []
        for i in range(0, len(objs), per):
            chunk = objs[i:i+per]
            modules.append({
                "title": f"Module {len(modules)+1}",
                "summary": f"Auto chunk from {chunk[0]['name']} to {chunk[-1]['name']}",
                "est_minutes": 45,
                "items": [{"objective": o["name"], "success_criteria": ", ".join(o.get("success", []))} for o in chunk]
            })
        return {"modules": modules}
