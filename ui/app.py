import os, json, requests, streamlit as st

API = os.getenv("AGI_TUTOR_API_BASE", "https://agi-tutor.onrender.com")
BUILD_TAG = "UI-build: 2025-10-16-12:05Z"

try:
    from agi_tutor.agi_agent import build_system_prompt, call_model  # type: ignore
except Exception:
    build_system_prompt = None
    call_model = None

st.set_page_config(page_title=f"AGI Tutor • {BUILD_TAG}", layout="wide")

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

if API_MODE:
    st.title(f"AGI Tutor • Backend mode · {BUILD_TAG}")

    name = qget("name", "Archie")
    region = qget("region", "Wales")
    stage = qget("stage", "Year 8")
    subject_code = qget("subject_code", "maths")
    hpw = float(qget("hours_per_week", "2"))
    spw = int(qget("sessions_per_week", "2"))
    start_date = qget("start_date", "2025-09-01")
    end_date = qget("end_date", "2026-06-30")
    autostart = qget("autostart", "0") == "1"

    with st.sidebar:
        st.header("Learner")
        name = st.text_input("Name", name)
        region = st.text_input("Region", region)
        stage = st.text_input("Stage", stage)
        st.caption(f"Subject: {subject_code} · HPW: {hpw} · SPW: {spw}")
        st.caption(f"{start_date} → {end_date}")

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
                    hours_per_session=1.0, sessions_per_week=spw, school_year_end=end_date
                )
                st.query_params["user_id"] = str(st.session_state.user_id)
                st.success(f"user_id = {st.session_state.user_id}")
            except requests.HTTPError as e:
                st.error(f"/signup failed: {e.response.text}")
                st.stop()

        if st.button("Ensure plan"):
            try:
                # KEY: keyword args avoid any positional mixups
                api_plan(
                    user_id=st.session_state.user_id,
                    subject_code=subject_code,
                    hours_per_week=hpw,
                    start_date=start_date,
                    end_date=end_date,
                )
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

        start_now = autostart or st.button("Start session")
        if start_now:
            try:
                sess = api_session_start(user_id=st.session_state.user_id, module_id=picked["id"])
            except requests.HTTPError as e:
                st.error(f"/session/start failed: {e.response.text}")
                st.stop()

            st.success("Session payload")
            st.json(sess)
            st.caption("This is your module/session JSON from the backend.")

            if build_system_prompt and call_model:
                module = sess.get("module", {})
                items = module.get("items", [])
                context = {
                    "student": {"name": name, "region": region, "stage": stage},
                    "time": {"sessions_per_week": spw, "hours_per_session": 1.0, "school_year_end": end_date},
                    "curriculum_topic": module.get("title", subject_code),
                    "must_cover": items,
                }
                sys_prompt = build_system_prompt(context)
                st.session_state.api_messages = [
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": f"Hi! Start the session for {name}. Greet me, set today’s goal, and ask the first question."}
                ]
                first = call_model(st.session_state.api_messages)
                st.session_state.api_messages.append({"role": "assistant", "content": first})

        if "api_messages" in st.session_state and st.session_state.api_messages and call_model:
            st.divider()
            st.subheader("Tutor session")
            for m in st.session_state.api_messages:
                if m["role"] == "assistant":
                    st.chat_message("assistant").write(m["content"])
                elif m["role"] == "user":
                    st.chat_message("user").write(m["content"])
            user_msg = st.chat_input("Type your answer or question")
            if user_msg:
                st.session_state.api_messages.append({"role": "user", "content": user_msg})
                reply = call_model(st.session_state.api_messages)
                st.session_state.api_messages.append({"role": "assistant", "content": reply})
                st.rerun()

    st.stop()

st.title(f"AGI Tutor (local demo) · {BUILD_TAG}")
st.info("Run this app with query string `?api=1` to use the backend service.")
st.write("Example: `.../app?api=1&subject_code=maths&hours_per_week=2&sessions_per_week=2&autostart=1`")
