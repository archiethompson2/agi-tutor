import os, json, requests, streamlit as st

API = os.getenv("AGI_TUTOR_API_BASE", "https://agi-tutor.onrender.com")

st.title("AGI Tutor • API Smoke Test")

try:
    h = requests.get(f"{API}/health", timeout=10).json()
    st.success(f"/health OK: {h}")
except Exception as e:
    st.error(f"/health failed: {e}")
    st.stop()

resp = requests.post(f"{API}/signup", json={
    "name":"SmokeTest",
    "region":"Wales",
    "stage":"Year 8",
    "hours_per_session":1.0,
    "sessions_per_week":2,
    "school_year_end":"2026-06-30"
}, timeout=20).json()
user_id = resp["user_id"]
st.write({"user_id": user_id})

plan = requests.post(f"{API}/plan", json={
    "user_id": user_id,
    "subject_code": "maths",
    "hours_per_week": 2,
    "sessions_per_week": 2,
    "start_date": "2025-09-01",
    "end_date": "2026-06-30"
}, timeout=30).json()
st.write(plan)

mods = requests.get(f"{API}/modules", params={
    "user_id": user_id,
    "subject_code": "maths"
}, timeout=20).json()
st.json(mods)

mods_list = mods.get("modules", [])
if not mods_list:
    st.stop()

module_id = mods_list[0]["id"]
sess = requests.post(f"{API}/session/start", json={
    "user_id": user_id,
    "module_id": module_id
}, timeout=20).json()
st.subheader("Session payload")
st.json(sess)
