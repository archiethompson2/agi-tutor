from __future__ import annotations
import httpx

DEFAULT_BASE = "http://127.0.0.1:8000"

def get_modules(user_id: int, subject_code: str, base: str = DEFAULT_BASE) -> dict:
    r = httpx.get(f"{base}/modules", params={"user_id": user_id, "subject_code": subject_code}, timeout=20.0)
    r.raise_for_status()
    return r.json()

def session_start(user_id: int, module_id: int, base: str = DEFAULT_BASE) -> dict:
    r = httpx.post(f"{base}/session/start", json={"user_id": user_id, "module_id": module_id}, timeout=20.0)
    r.raise_for_status()
    return r.json()
