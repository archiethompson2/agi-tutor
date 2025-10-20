import json
from pathlib import Path
from typing import Dict, Any, Iterable, List, Tuple

def _norm(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "").replace("-", "").replace("/", "")

def _candidate_names(region: str, year: str, subject: str) -> List[str]:
    r, y, sub = _norm(region), _norm(year), _norm(subject)
    return [
        f"{sub}_{y}_{r}.json",
        f"{sub}_{r}_{y}.json",
        f"{r}_{y}_{sub}.json",
        f"{sub}.json",
    ]

def _candidate_dirs() -> List[Path]:
    here = Path(__file__).resolve()
    pkg = here.parent              # .../src/agi_tutor
    project = Path.cwd()           # runtime CWD (Render: /opt/render/project/src)
    fixed = Path("/opt/render/project/src")
    return list(dict.fromkeys([
        pkg / "curriculums",
        project / "agi_tutor" / "curriculums",
        project / "data" / "curriculums",
        fixed / "agi_tutor" / "curriculums",
        fixed / "data" / "curriculums",
    ]))

def _iter_candidates(region: str, year: str, subject: str) -> Iterable[Path]:
    for d in _candidate_dirs():
        for name in _candidate_names(region, year, subject):
            yield d / name

def load_curriculum(region: str, year: str, subject: str) -> Dict[str, Any]:
    errors: List[Tuple[str, str]] = []
    for p in _iter_candidates(region, year, subject):
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                print(f"[curriculum] loaded: {p}")
                return data
        except Exception as e:
            errors.append((str(p), f"{type(e).__name__}: {e}"))

    # Fallbacks
    fallbacks = [
        Path.cwd() / "data" / "curriculums" / ("maths.json" if _norm(subject) == "maths" else "curriculum.json"),
        Path("/opt/render/project/src/data/curriculums") / ("maths.json" if _norm(subject) == "maths" else "curriculum.json"),
    ]
    for p in fallbacks:
        try:
            if p.exists():
                data = json.loads(p.read_text(encoding="utf-8"))
                print(f"[curriculum] fallback loaded: {p}")
                return data
        except Exception as e:
            errors.append((str(p), f"{type(e).__name__}: {e}"))

    if errors:
        print("[curriculum] failed to load any curriculum. Tried:")
        for path, err in errors:
            print(f" - {path} -> {err}")
    return {}

# --- DEBUG: expose what paths are considered and whether they exist
def debug_candidates(region: str, year: str, subject: str):
    out = []
    for p in _iter_candidates(region, year, subject):
        try:
            exists = p.exists()
            size = p.stat().st_size if exists else 0
            out.append({"path": str(p), "exists": exists, "size": size})
        except Exception as e:
            out.append({"path": str(p), "exists": False, "error": f"{type(e).__name__}: {e}"})
    return out
