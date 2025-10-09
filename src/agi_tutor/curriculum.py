from __future__ import annotations
from pathlib import Path
import json
from typing import Any

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

def load_curriculum(region: str, year: str, subject_code: str) -> dict[str, Any]:
    # Naming convention, tweak if needed
    fname = f"{year}_{region}_{subject_code.title()}.json".replace(" ", "")
    # e.g. Year8_Wales_Maths.json
    path = DATA_DIR / fname
    if not path.exists():
        # fallback to your existing file layout for maths Wales Year 8
        alt = DATA_DIR / "Year8_Wales_Maths.json"
        if alt.exists():
            path = alt
        else:
            raise FileNotFoundError(f"Missing curriculum spec {path}")
    return json.loads(path.read_text())

# Fallback Curriculum class (safe dummy for compatibility)
try:
    from dataclasses import dataclass
    @dataclass
    class Curriculum:
        subject: str
        stage: str
        region: str
        modules: list
except Exception:
    pass

# --- Safe planner helper ---
def to_plan_items(curr):
    """
    Build a flat list of plan items from a curriculum object or dict.
    Accepts shapes like:
      curr.modules = [ { "title": "...", "objectives": [ { "objective": "...", "success_criteria": "..." }, ... ] }, ... ]
    or
      { "modules": [...]} or { "topics": [...] }
    Returns a list of dicts with keys: title, objective, module, success_criteria
    """
    items = []

    # accept either dataclass-like object or plain dict
    modules = getattr(curr, "modules", None)
    if modules is None and isinstance(curr, dict):
        modules = curr.get("modules") or curr.get("topics") or []

    for mod in modules or []:
        # mod may be dict or object
        mod_title = None
        if isinstance(mod, dict):
            mod_title = mod.get("title") or mod.get("name") or "Module"
            objectives = mod.get("objectives") or mod.get("items") or []
        else:
            mod_title = getattr(mod, "title", None) or getattr(mod, "name", None) or "Module"
            objectives = getattr(mod, "objectives", None) or getattr(mod, "items", None) or []

        for obj in objectives:
            if isinstance(obj, dict):
                objective = obj.get("objective") or obj.get("name") or obj.get("title") or str(obj)
                success = obj.get("success_criteria") or obj.get("success") or None
            else:
                objective = str(obj)
                success = None

            items.append({
                "title": f"{mod_title} — {objective}",
                "objective": objective,
                "module": mod_title,
                "success_criteria": success
            })

    return items
