from __future__ import annotations
import json
import os
from typing import Dict, Any, List

def _read_json(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_curriculum(region: str, year: str, subject: str) -> dict:
    region_key = region.strip().lower()
    year_key = year.strip().lower().replace(" ", "")
    subject_key = subject.strip().lower()

    candidates: List[str] = []

    # explicit new folder form
    candidates.append(os.path.join("src", "agi_tutor", "curriculums", f"{subject_key}_{year_key}_{region_key}.json"))
    candidates.append(os.path.join("src", "agi_tutor", "curriculums", f"{subject_key}_{year_key}.json"))
    candidates.append(os.path.join("src", "agi_tutor", "curriculums", f"{subject_key}.json"))

    # legacy single file that you had earlier
    # e.g. data/Year8_Wales_Maths.json
    legacy = os.path.join("data", f"{year.replace(' ', '')}_{region}_{subject.capitalize()}.json")
    candidates.append(legacy)

    for p in candidates:
        if os.path.isfile(p):
            return _read_json(p)

    # graceful fallback so API does not 500
    return {
        "subject": subject,
        "stage": year,
        "region": region,
        "objectives": [
            {"name": "Placeholder Objective 1", "success": ["Understand key idea"]},
            {"name": "Placeholder Objective 2", "success": ["Practise simple problems"]}
        ]
    }

def to_plan_items(spec: Dict[str, Any]) -> List[Dict[str, Any]]:
    items = []
    for idx, o in enumerate(spec.get("objectives", []), start=1):
        items.append({
            "order": idx,
            "objective": o.get("name", f"Objective {idx}"),
            "success_criteria": ", ".join(o.get("success", []))
        })
    return items
