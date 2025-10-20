import json, hashlib
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
    pkg = here.parent              # e.g. /opt/render/project/src/src/agi_tutor
    project = Path.cwd()           # e.g. /opt/render/project/src
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

# --- DEBUG helpers
def _sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def debug_candidates(region: str, year: str, subject: str):
    out = []
    for p in _iter_candidates(region, year, subject):
        rec = {"path": str(p), "exists": False, "size": 0, "sha256": None, "parse_ok": False, "modules_detected": 0, "error": None}
        try:
            if p.exists():
                rec["exists"] = True
                b = p.read_bytes()
                rec["size"] = len(b)
                rec["sha256"] = _sha256_bytes(b)
                try:
                    data = json.loads(b.decode("utf-8"))
                    rec["parse_ok"] = True
                    if isinstance(data, dict) and isinstance(data.get("modules"), list):
                        rec["modules_detected"] = len(data["modules"])
                except Exception as e:
                    rec["error"] = f"{type(e).__name__}: {e}"
        except Exception as e:
            rec["error"] = f"{type(e).__name__}: {e}"
        out.append(rec)
    return out
