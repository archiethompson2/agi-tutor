from __future__ import annotations
from datetime import date
from typing import Any, Dict, List

from .curriculum import load_curriculum

def _normalize_modules(mods: List[Dict[str, Any]]) -> Dict[str, Any]:
    out: List[Dict[str, Any]] = []
    for m in mods or []:
        mm = {
            "title": m.get("title", "Module"),
            "summary": m.get("summary", ""),
            "est_minutes": int(m.get("est_minutes", 45)),
            "items": []
        }
        items = m.get("items", []) or []
        for idx, it in enumerate(items):
            mm["items"].append({
                "objective": it.get("objective", f"Objective {idx+1}"),
                "success_criteria": it.get("success_criteria", ""),
                "order_index": int(it.get("order_index", idx)),
            })
        out.append(mm)
    return {"modules": out}

def _placeholder_plan() -> Dict[str, Any]:
    print("[planner] WARNING: using placeholder plan (no curriculum modules found)")
    return {
        "modules": [{
            "title": "Introduction to Key Concepts",
            "summary": "An overview of essential mathematical ideas.",
            "est_minutes": 30,
            "items": [{"objective": "Placeholder Objective 1", "success_criteria": "Understand key idea", "order_index": 0}]
        }]
    }

def make_plan(
    name: str,
    region: str,
    year: str,
    subject: str,
    hours_per_week: float,
    start: date,
    end: date
) -> Dict[str, Any]:
    """
    Returns a plan dict: {"modules": [ ... ]}
    Priority:
      1) Use prebuilt curriculum modules if present and non-empty
      2) If objectives-only spec, convert to one module
      3) Fallback placeholder
    """
    spec = load_curriculum(region, year, subject)

    # 1) Prebuilt modules if non-empty
    if isinstance(spec, dict) and isinstance(spec.get("modules"), list) and len(spec["modules"]) > 0:
        return _normalize_modules(spec["modules"])

    # 2) Legacy objectives → single module
    if isinstance(spec, dict) and isinstance(spec.get("objectives"), list) and len(spec["objectives"]) > 0:
        mods = [{
            "title": f"{subject.title()} Core Objectives",
            "summary": f"Auto-generated module from objectives for {subject} ({region} {year}).",
            "est_minutes": max(45, int(60 * max(1, len(spec.get('objectives', [])) // 4))),
            "items": [
                {
                    "objective": o.get("objective", f"Objective {i+1}"),
                    "success_criteria": o.get("success_criteria", ""),
                    "order_index": i
                }
                for i, o in enumerate(spec.get("objectives", []))
            ]
        }]
        return _normalize_modules(mods)

    # 3) Fallback
    return _placeholder_plan()
