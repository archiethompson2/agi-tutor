from __future__ import annotations
from datetime import date
from typing import Any, Dict, List

# Uses your existing loader
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
    Returns a plan dict: {"modules": [ {title, summary, est_minutes, items:[{objective, success_criteria, order_index}]} ]}
    Priority:
      1) Use prebuilt curriculum modules if present (e.g. data/curriculums/maths.json or region/year specific file)
      2) Fallback to any legacy/objective-based logic in load_curriculum (normalize if possible)
      3) Final fallback: single placeholder module
    """
    spec = load_curriculum(region, year, subject)

    # 1) Prebuilt modules path
    if isinstance(spec, dict) and spec.get("modules"):
        return _normalize_modules(spec["modules"])

    # 2) Legacy shape: try to turn objectives into modules if present
    #    e.g. {"objectives":[{"objective":..., "success_criteria":...}, ...]}
    if isinstance(spec, dict) and spec.get("objectives"):
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
