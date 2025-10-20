import os, json, requests, streamlit as st

API = os.getenv("AGI_TUTOR_API_BASE", "https://agi-tutor.onrender.com")
BUILD_TAG = "UI-build: 2025-10-20-15:40Z"

# Optional: import the tutor agent for chat handoff
try:
    from agi_tutor.agi_agent import build_system_prompt, call_model  # type: ignore
except Exception:
    build_system_prompt = None
    call_model = None

# Explain in the UI why the tutor may be disabled
TUTOR_READY = bool(build_system_prompt and call_model)
with st.sidebar:
    st.caption(f"Tutor status — ready: {TUTOR_READY} • model: {os.getenv('OPENAI_MODEL', 'unset')} • key: {'set' if os.getenv('OPENAI_API_KEY') else 'missing'}")

st.set_page_config(page_title=f"AGI Tutor • {BUILD_TAG}", layout="wide")

# Query param helper
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

# ------------------- API mode UI -------------------
if API_MODE:
    st.title(f"AGI Tutor • Backend mode • {BUILD_TAG}")

    # Read from query string but expose REAL inputs to avoid bad values
    default_subject = qget("subject_code", "maths")
    default_hpw = float(qget("hours_per_week", "2"))
    default_spw = int(qget("sessions_per_week", "2"))
    default_start = qget("start_date", "2025-09-01")
    default_end = qget("end_date", "2026-06-30")
    default_name = qget("name", "Archie")
    default_region = qget("region", "Wales")
    default_stage = qget("stage", "Year 8")

    with st.sidebar:
        st.header("Learner")
        name = st.text_input("Name", default_name)
        region = st.text_input("Region", default_region)
        stage = st.text_input("Stage", default_stage)

        subject_code = st.selectbox("Subject", ["maths"], index=0 if default_subject == "maths" else 0)
        hpw = st.number_input("Hours per week", min_value=0.5, max_value=20.0, step=0.5, value=float(default_hpw))
        spw = st.number_input("Sessions per week", min_value=1, max_value=14, step=1, value=int(default_spw))
        start_date = st.text_input("Start date (YYYY-MM-DD)", default_start)
        end_date = st.text_input("End date (YYYY-MM-DD)", default_end)

    col1, col2 = st.columns([2, 3])

    with col1:
        st.subheader("Create / ensure")

        if "user_id" not in st.session_state:
            try:
                st.session_state.user_id = int(qp.get("user_id", [0])[0])
            except Exception:
                st.session_state.user_id = 0

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

        plan_payload = {
            "user_id": int(st.session_state.user_id or 0),
            "subject_code": subject_code,
            "hours_per_week": float(hpw),
            "start_date": start_date,
            "end_date": end_date,
        }
        with st.expander("Plan payload (what will be POSTed to /plan)"):
            st.json(plan_payload)

        if st.button("Ensure plan"):
            try:
                api_plan(**plan_payload)
                st.success("Plan ensured")
            except requests.HTTPError as e:
                st.error(f"/plan failed: {e.response.text}")
                st.stop()

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
        if autostart or st.button("Start session"):
            try:
                sess = api_session_start(user_id=st.session_state.user_id, module_id=picked["id"])
            except requests.HTTPError as e:
                st.error(f"/session/start failed: {e.response.text}")
                st.stop()

            st.success("Session payload")
            st.json(sess)
            st.caption("This is your module/session JSON from the backend.")
            if not TUTOR_READY:
                st.warning("Tutor agent is disabled. Set OPENAI_API_KEY on the UI service and redeploy.")
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
                try:
                    first = call_model(st.session_state.api_messages)
                except Exception as e:
                    st.error(f"Tutor call failed on first turn: {e}")
                    st.stop()
                st.session_state.api_messages.append({"role": "assistant", "content": first})

        if TUTOR_READY and "api_messages" in st.session_state and st.session_state.api_messages and call_model:
    st.divider()
    st.subheader("Tutor session")
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
        st.session_state.api_messages.append({"role": "assistant", "content": reply})
        st.rerun()

    st.stop()

# -------- Local demo fallback --------
st.title(f"AGI Tutor (local demo) • {BUILD_TAG}")
st.info("Run this app with query string `?api=1` to use the backend service.")
st.write("Example: `.../app?api=1&subject_code=maths&hours_per_week=2&sessions_per_week=2&autostart=1`")
