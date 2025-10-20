import json, os
from pathlib import Path
from typing import Dict, Any

# NOTE: Runtime CWD on Render is /opt/render/project/src
# Package files live under: agi_tutor/...
# Data lives under: data/...
BASE1 = Path("agi_tutor/curriculums")
BASE2 = Path("data/curriculums")

def _norm(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "").replace("-", "").replace("/", "")

def _candidates(region: str, year: str, subject: str):
    r, y, sub = _norm(region), _norm(year), _norm(subject)
    files = [
        f"{sub}_{y}_{r}.json",
        f"{sub}_{r}_{y}.json",
        f"{r}_{y}_{sub}.json",
        f"{sub}.json",
    ]
    for f in files:
        yield BASE1 / f
    for f in files:
        yield BASE2 / f

def load_curriculum(region: str, year: str, subject: str) -> Dict[str, Any]:
    for p in _candidates(region, year, subject):
        if p.exists():
            try:
                return json.loads(p.read_text())
            except Exception:
                pass
    # Final defensive fallback: maths.json for maths, else generic
    p = BASE2 / ("maths.json" if _norm(subject) == "maths" else "curriculum.json")
    if p.exists():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}
