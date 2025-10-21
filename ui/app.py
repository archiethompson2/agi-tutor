import os, json, requests, streamlit as st

API = os.getenv("AGI_TUTOR_API_BASE", "https://agi-tutor.onrender.com")
BUILD_TAG = "UI-build: 2025-10-21-17:55Z"

# Optional: import the tutor agent for chat handoff
# Ensure the project src/ is on sys.path (Render/Streamlit sometimes misses it)
import sys, pathlib, email.utils
_IMPORT_ERR = None
try:
    _PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
    _SRC = _PROJECT_ROOT / "src"
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))
    from agi_tutor.agi_agent import build_system_prompt, call_model, split_assessment  # type: ignore
except Exception as e:
    build_system_prompt = None
    call_model = None
    split_assessment = None
    _IMPORT_ERR = f"{type(e).__name__}: {e}"

# Tutor status + SIMULATE switch (lets you test chat loop even without OpenAI)
TUTOR_READY = bool(build_system_prompt and call_model)
SIMULATE = (os.getenv("SIMULATE_TUTOR", "0") == "1")
if SIMULATE:
    def call_model(msgs):
        last_usr = ""
        for m in msgs[::-1]:
            if m["role"] == "user":
                last_usr = m["content"]
                break
        # Emit a valid [[ASSESSMENT]] block
        return (
            f"Okay — I heard: {last_usr}\n\n"
            "[[ASSESSMENT]]"
            "{"
            "\"item_index\": 0, "
            "\"objective\": \"Sim objective\", "
            "\"mastery_estimate\": 0.5, "
            "\"confidence\": 0.5, "
            "\"last_response_correct\": true, "
            "\"ready_to_advance\": false, "
            "\"needs_more_practice\": true"
            "}"
            "[[/ASSESSMENT]]"
        )
    # Minimal inline split to allow SIMULATE without agi_agent import
    if split_assessment is None:
        import re, json as _json
        ASSESSMENT_START, ASSESSMENT_END = "[[ASSESSMENT]]", "[[/ASSESSMENT]]"
        def split_assessment(text: str):
            pat = re.compile(re.escape(ASSESSMENT_START) + r"(.*?)" + re.escape(ASSESSMENT_END), re.DOTALL)
            m = pat.search(text or "")
            assess = {}
            if m:
                try:
                    assess = _json.loads(m.group(1).strip())
                except Exception:
                    assess = {}
                text = pat.sub("", text).strip()
            return text, assess
    TUTOR_READY = True

st.set_page_config(page_title=f"AGI Tutor • {BUILD_TAG}", layout="wide")

# Query params (Streamlit v1.50 has st.query_params)
try:
    qp = st.query_params
except Exception:
    qp = {}

def qget(name: str, default: str) -> str:
    try:
        return qp.get(name, [default])[0]
    except Exception:
        return default

API_MODE = qget("api", "0") == "1"

# ------------------- Backend calls -------------------
def api_signup(name, region, stage, hours_per_session, sessions_per_week, school_year_end):
    payload = {
        "name": name,
        "region": region,
        "stage": stage,
        "hours_per_session": hours_per_session,
        "sessions_per_week": sessions_per_week,
        "school_year_end": school_year_end,
    }
    r = requests.post(f"{API}/signup", json=payload, timeout=30)
    r.raise_for_status()
    return int(r.json()["user_id"])

def api_plan(user_id, subject_code, hours_per_week, start_date, end_date):
    payload = {
        "user_id": user_id,
        "subject_code": subject_code,
        "hours_per_week": hours_per_week,
        "start_date": start_date,
        "end_date": end_date,
    }
    r = requests.post(f"{API}/plan", json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

def api_modules(user_id, subject_code):
    r = requests.get(f"{API}/modules", params={"user_id": user_id, "subject_code": subject_code}, timeout=30)
    r.raise_for_status()
    return r.json().get("modules", [])

def api_session_start(user_id, module_id):
    r = requests.post(f"{API}/session/start", json={"user_id": user_id, "module_id": module_id}, timeout=45)
    r.raise_for_status()
    return r.json()

def api_session_complete(payload: dict):
    r = requests.post(f"{API}/session/complete", json=payload, timeout=45)
    r.raise_for_status()
    return r.json()

def api_metrics_module(user_id: int, module_id: int):
    r = requests.get(f"{API}/metrics/module", params={"user_id": user_id, "module_id": module_id}, timeout=30)
    r.raise_for_status()
    return r.json()

# ------------------- UI -------------------
st.title(f"AGI Tutor • {BUILD_TAG}")

# Sidebar: persistent status for tutor agent config
with st.sidebar:
    st.caption(
        f"Tutor status — ready: {TUTOR_READY} • "
        f"model: {os.getenv('OPENAI_MODEL','unset')} • "
        f"key: {'set' if os.getenv('OPENAI_API_KEY') else 'missing'} • "
        f"simulate: {SIMULATE}"
    )
    # Show why tutor is disabled if not in SIMULATE mode
    if not TUTOR_READY and os.getenv('SIMULATE_TUTOR','0') != '1':
        if _IMPORT_ERR:
            st.warning(f"Agent import failed: {_IMPORT_ERR}")
        elif not os.getenv('OPENAI_API_KEY'):
            st.warning('OPENAI_API_KEY is missing on the UI service.')

if API_MODE:
    # Read from query string but expose inputs so params can be fixed in UI
    default_subject = qget("subject_code", "maths")
    default_hpw = float(qget("hours_per_week", "2"))
    default_spw = int(qget("sessions_per_week", "2"))
    default_start = qget("start_date", "2025-09-01")
    default_end = qget("end_date", "2026-06-30")
    default_name = qget("name", "Archie")
    default_region = qget("region", "Wales")
    default_stage = qget("stage", "Year 8")

    # Session-state init: always present so chat loop cannot break
    if "user_id" not in st.session_state:
        try:
            st.session_state.user_id = int(qp.get("user_id", [0])[0])
        except Exception:
            st.session_state.user_id = 0
    if "api_messages" not in st.session_state:
        st.session_state.api_messages = []
    if "session_started" not in st.session_state:
        st.session_state.session_started = False
    if "progress" not in st.session_state:
        st.session_state.progress = {"module_id": None, "items": [], "started_at": None}
    if "module_meta" not in st.session_state:
        st.session_state.module_meta = {"title": "", "items_total": 0}

    # --- Sidebar learner fields
    with st.sidebar:
        st.header("Learner")
        name = st.text_input("Name", default_name)
        region = st.text_input("Region", default_region)
        stage = st.text_input("Stage", default_stage)

        subject_code = st.selectbox("Subject", ["maths"], index=0)
        hpw = st.number_input("Hours per week", min_value=0.5, max_value=20.0, step=0.5, value=float(default_hpw))
        spw = st.number_input("Sessions per week", min_value=1, max_value=14, step=1, value=int(default_spw))
        start_date = st.text_input("Start date (YYYY-MM-DD)", default_start)
        end_date = st.text_input("End date (YYYY-MM-DD)", default_end)

    col1, col2 = st.columns([2, 3])

    # -------- Left: create/ensure ----------
    with col1:
        st.subheader("Create / ensure")

        if st.button("Create user") or st.session_state.user_id == 0:
            try:
                st.session_state.user_id = api_signup(
                    name=name, region=region, stage=stage,
                    hours_per_session=1.0, sessions_per_week=int(spw), school_year_end=end_date
                )
                st.query_params["user_id"] = str(st.session_state.user_id)
                st.success(f"user_id = {st.session_state.user_id}")
            except requests.HTTPError as e:
                st.error(f"/signup failed: {e.response.text}")
                st.stop()
            except Exception as e:
                st.error(f"/signup failed: {e}")
                st.stop()

        plan_payload = {
            "user_id": int(st.session_state.user_id or 0),
            "subject_code": subject_code,
            "hours_per_week": float(hpw),
            "start_date": start_date,
            "end_date": end_date,
        }
        with st.expander("Plan payload (POST /plan)"):
            st.json(plan_payload)

        if st.button("Ensure plan"):
            try:
                api_plan(**plan_payload)
                st.success("Plan ensured")
            except requests.HTTPError as e:
                st.error(f"/plan failed: {e.response.text}")
                st.stop()
            except Exception as e:
                st.error(f"/plan failed: {e}")
                st.stop()

    # -------- Right: modules + session ----------
    with col2:
        st.subheader("Modules")
        try:
            mods = api_modules(st.session_state.user_id, subject_code)
        except Exception as e:
            st.error(f"fetch modules failed: {e}")
            mods = []

        if not mods:
            st.info("No modules yet. Click Ensure plan.")
            st.stop()

        titles = [m.get("title", f"Module {i+1}") for i, m in enumerate(mods)]
        idx = st.selectbox("Pick a module", list(range(len(mods))), format_func=lambda i: titles[i])
        picked = mods[idx]
        with st.expander("Selected module payload"):
            st.json(picked)

        autostart = qget("autostart", "0") == "1"
        if ((autostart and not st.session_state.session_started) or st.button("Start session")):
            try:
                sess = api_session_start(user_id=st.session_state.user_id, module_id=picked["id"])
            except requests.HTTPError as e:
                st.error(f"/session/start failed: {e.response.text}")
                st.stop()
            except Exception as e:
                st.error(f"/session/start failed: {e}")
                st.stop()

            st.success("Session payload")
            st.json(sess)
            st.caption("This is your module/session JSON from the backend.")

            if not TUTOR_READY:
                st.warning("Tutor agent is disabled. Set OPENAI_API_KEY on the UI service and redeploy (or SIMULATE_TUTOR=1).")
                st.stop()

            if build_system_prompt and call_model:
                module = sess.get("module", {})
                items = module.get("items", [])
                context = {
                    "student": {"name": name, "region": region, "stage": stage},
                    "time": {"sessions_per_week": int(spw), "hours_per_session": 1.0, "school_year_end": end_date},
                    "curriculum_topic": module.get("title", subject_code),
                    "must_cover": items,
                }
                sys_prompt = build_system_prompt(context)
                st.session_state.api_messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Hi! Start the session for {name}. Greet me, set today’s goal, and ask the first question."}
                ]
                st.session_state.session_started = True
                st.session_state.progress = {
                    "module_id": picked["id"],
                    "items": [{"objective": it.get("objective",""), "events": []} for it in items],
                    "started_at": email.utils.formatdate(usegmt=False)
                }
                st.session_state.module_meta = {"title": module.get("title",""), "items_total": len(items)}
                try:
                    # clear autostart=1 so future reruns don't reset the chat
                    try:
                        st.query_params["autostart"] = "0"
                    except Exception:
                        pass
                    first = call_model(st.session_state.api_messages)
                except Exception as e:
                    st.error(f"Tutor call failed on first turn: {e}")
                    st.stop()
                st.session_state.api_messages.append({"role": "assistant", "content": first})

    # -------- Chat area (always visible once messages exist) ----------
    if TUTOR_READY and st.session_state.get("api_messages") and call_model:
        st.divider()
        left, right = st.columns([3,2])
        with left:
            st.subheader("Tutor session")
        with right:
            prog = st.session_state.progress
            items_total = st.session_state.module_meta.get("items_total", 0) or 0
            mastered = 0
            confidences = []
            for it in prog.get("items", []):
                if it["events"]:
                    confidences.extend([e.get("confidence",0.0) for e in it["events"]])
                    recent = it["events"][-2:]
                    mean_recent = sum(e.get("confidence",0.0) for e in recent) / len(recent)
                    if mean_recent >= 0.70:
                        mastered += 1
            avg_conf = (sum(confidences)/len(confidences)) if confidences else 0.0
            st.caption(f"**Progress** · {mastered}/{items_total} mastered • avg confidence {avg_conf:.2f}")

        for m in st.session_state.api_messages:
            st.chat_message(m["role"]).write(m["content"])

        user_msg = st.chat_input("Type your answer or question")
        if user_msg:
            st.session_state.api_messages.append({"role": "user", "content": user_msg})
            try:
                reply = call_model(st.session_state.api_messages)
            except Exception as e:
                st.error(f"Tutor call failed: {e}")
                st.stop()
            text, assess = split_assessment(reply) if split_assessment else (reply, {})
            st.session_state.api_messages.append({"role": "assistant", "content": text or reply})
            try:
                if isinstance(assess, dict):
                    i = int(assess.get("item_index", 0))
                    if 0 <= i < len(st.session_state.progress["items"]):
                        st.session_state.progress["items"][i]["events"].append({
                            "ts": email.utils.formatdate(usegmt=False),
                            "last_response_correct": assess.get("last_response_correct"),
                            "confidence": float(assess.get("confidence", 0.0)),
                            "mastery_estimate": float(assess.get("mastery_estimate", 0.0)),
                        })
            except Exception:
                pass
            st.rerun()

        # --- End Session: persist rollups ---
        st.divider()
        if st.button("End Session", type="primary"):
            prog = st.session_state.progress
            items = prog.get("items", [])
            events_payload, confidences = [], []
            mastered = 0
            for idx, it in enumerate(items):
                evs = it["events"]
                for e in evs:
                    confidences.append(e.get("confidence", 0.0))
                    events_payload.append({
                        "item_index": idx,
                        "last_response_correct": e.get("last_response_correct"),
                        "confidence": float(e.get("confidence", 0.0)),
                        "mastery_estimate": float(e.get("mastery_estimate", 0.0)),
                        "ts": e.get("ts"),
                    })
                if evs:
                    recent = evs[-2:]
                    mean_recent = sum(e.get("confidence",0.0) for e in recent)/len(recent)
                    if mean_recent >= 0.70:
                        mastered += 1
            avg_conf = (sum(confidences)/len(confidences)) if confidences else 0.0
            payload = {
                "user_id": int(st.session_state.user_id),
                "module_id": int(prog.get("module_id") or 0),
                "time_spent_min": max(1.0, len(events_payload) * 1.0),
                "mastery_estimate": float(min(1.0, (mastered / max(1, len(items))) if items else 0.0)),
                "avg_confidence": float(avg_conf),
                "items_total": int(len(items)),
                "items_mastered": int(mastered),
                "events": events_payload,
            }
            try:
                api_session_complete(payload)
                st.success("Session saved.")
                try:
                    m = api_metrics_module(st.session_state.user_id, prog.get("module_id") or 0)
                    st.info(
                        f"Latest roll-up • {m.get('items_mastered',0)}/{m.get('items_total',0)} mastered • "
                        f"avg confidence {m.get('avg_confidence',0.0):.2f} • "
                        f"time {m.get('time_spent_min',0.0):.1f} min"
                    )
                except Exception:
                    pass
            except Exception as e:
                st.error(f"/session/complete failed: {e}")

# -------- Local demo fallback --------
if not API_MODE:
    st.info("Run with `?api=1` to use the backend service. Example:")
    st.code(".../app?api=1&subject_code=maths&hours_per_week=2&sessions_per_week=2&autostart=1")
