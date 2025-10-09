from __future__ import annotations
from datetime import date
from typing import Any, List
import math, json

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

def _get_obj_list(spec: dict) -> list:
    return spec.get("objectives") or spec.get("items") or spec.get("topics") or []

def _fallback_modules(objs: list[dict], weeks: int) -> dict[str, Any]:
    per = max(1, math.ceil(len(objs) / max(1, weeks)))
    modules: list[dict[str, Any]] = []
    for i in range(0, len(objs), per):
        chunk = objs[i:i+per]
        modules.append({
            "title": f"Module {len(modules)+1}",
            "summary": f"Auto chunk from {chunk[0]['name']} to {chunk[-1]['name']}",
            "est_minutes": 45,
            "items": [
                {"objective": o["name"], "success_criteria": ", ".join(o.get("success", []))}
                for o in chunk
            ]
        })
    return {"modules": modules}

def make_plan(name: str, region: str, year: str, subject: str,
              hours_per_week: float, start: date, end: date) -> dict[str, Any]:
    spec = load_curriculum(region, year, subject)
    objs = _get_obj_list(spec)
    weeks = weeks_between(start, end)
    total_minutes = int(hours_per_week * 60 * weeks)

    user = {
        "student": {"name": name, "region": region, "year": year},
        "subject": subject,
        "timebox": {"weeks": weeks, "hours_per_week": hours_per_week, "total_minutes": total_minutes},
        "objectives": [
            {"objective": o.get("name"), "success_criteria": ", ".join(o.get("success", []))}
            for o in objs
        ]
    }

    # Try model plan, then parse, otherwise fall back deterministically
    try:
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": json.dumps(user)}
        ]
        out = call_model(messages)  # may raise if no OPENAI_API_KEY on Render
        start_i = out.find("{")
        end_i = out.rfind("}")
        if start_i != -1 and end_i != -1:
            payload = json.loads(out[start_i:end_i+1])
            if isinstance(payload, dict) and "modules" in payload:
                return payload
    except Exception:
        pass

    return _fallback_modules(objs, weeks)
