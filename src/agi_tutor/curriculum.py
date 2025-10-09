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
