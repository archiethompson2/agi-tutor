# === API_MODE (activate with ?api=1) ==========================================
# This block lets the main app call the live FastAPI backend when you open:
#   https://agi-tutor-1.onrender.com/?api=1
# It is isolated and won't affect normal behavior without ?api=1.
try:
    import os, json, requests, streamlit as st  # noqa: F401
    _qp = st.query_params if hasattr(st, "query_params") else {}
    _api_mode = (_qp.get("api", ["0"])[0] == "1")
except Exception:
    _api_mode = False

if _api_mode:
    import os, json, requests, streamlit as st

    API = os.getenv("AGI_TUTOR_API_BASE", "https://agi-tutor.onrender.com")
    st.set_page_config(page_title="AGI Tutor • Backend mode", layout="wide")
    st.title("AGI Tutor • Backend mode")

    # --- helpers --------------------------------------------------------------
    def api_signup(name, region, stage, hps, spw, sye):
        r = requests.post(f"{API}/signup", json={
            "name": name, "region": region, "stage": stage,
            "hours_per_session": hps, "sessions_per_week": spw,
            "school_year_end": sye
        }, timeout=20); r.raise_for_status(); return r.json()["user_id"]

    def api_plan(uid, subject_code, hpw, spw, start_date, end_date):
        r = requests.post(f"{API}/plan", json={
            "user_id": uid, "subject_code": subject_code,
            "hours_per_week": hpw, "sessions_per_week": spw,
            "start_date": start_date, "end_date": end_date
        }, timeout=30); r.raise_for_status(); return r.json()

    def api_modules(uid, subject_code):
        r = requests.get(f"{API}/modules", params={
            "user_id": uid, "subject_code": subject_code
        }, timeout=20); r.raise_for_status(); return r.json().get("modules", [])

    def api_session_start(uid, module_id):
        r = requests.post(f"{API}/session/start", json={
            "user_id": uid, "module_id": module_id
        }, timeout=20); r.raise_for_status(); return r.json()

    # --- query params with defaults ------------------------------------------
    qp = st.query_params
    name = qp.get("name", ["Archie"])[0]
    region = qp.get("region", ["Wales"])[0]
    stage = qp.get("stage", ["Year 8"])[0]
    subject_code = qp.get("subject_code", ["maths"])[0]
    hpw = float(qp.get("hours_per_week", [2])[0])
    spw = int(qp.get("sessions_per_week", [2])[0])
    start_date = qp.get("start_date", ["2025-09-01"])[0]
    end_date = qp.get("end_date", ["2026-06-30"])[0]

    with st.sidebar:
        st.header("Learner")
        name = st.text_input("Name", name)
        region = st.text_input("Region", region)
        stage = st.text_input("Stage", stage)
        st.caption(f"Subject: {subject_code} · HPW: {hpw} · SPW: {spw}")
        st.caption(f"{start_date} → {end_date}")

    col1, col2 = st.columns([2,3])

    with col1:
        st.subheader("Create / ensure")
        if "user_id" not in st.session_state:
            # allow pre-supplied uid via ?user_id=
            st.session_state.user_id = int(qp.get("user_id", [0])[0])

        if st.button("Create user") or st.session_state.user_id == 0:
            st.session_state.user_id = api_signup(name, region, stage, 1.0, spw, end_date)
            st.query_params["user_id"] = str(st.session_state.user_id)
        st.success(f"user_id = {st.session_state.user_id}")

        if st.button("Ensure plan"):
            api_plan(st.session_state.user_id, subject_code, hpw, spw, start_date, end_date)
            st.success("Plan ensured")

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

        titles = [m["title"] for m in mods]
        idx = st.selectbox("Pick a module", list(range(len(mods))), format_func=lambda i: titles[i])
        picked = mods[idx]
        st.json(picked)

        if st.button("Start session"):
            sess = api_session_start(st.session_state.user_id, picked["id"])
            st.success("Session payload")
            st.json(sess)
            st.caption("This is your module/session JSON from the backend.")
    st.stop()
# === end API_MODE ============================================================
import sys
import base64
from datetime import datetime
from pathlib import Path
import streamlit as st

# import path
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from agi_tutor.db import fetchall, fetchone, execute
from agi_tutor.planner import next_topic_for
from agi_tutor.agi_agent import build_system_prompt, call_model, split_assessment, recover_assessment
from agi_tutor.guardrails import autograde  # <-- NEW

MASTERY_TARGET = 0.85
MODEL_CONF_WEIGHT = 0.6

# NEW, strict marking rule injected at session start
STRICT_RULES = (
    "Tutor rules: If the learner's last message contains the correct final answer, "
    "confirm it clearly, explain briefly, and move on. Do not ask them to recompute an already "
    "correct answer. Always include an assessment JSON in responses with fields "
    "last_response_correct, mastery_estimate, confidence, ready_to_advance."
)

st.set_page_config(page_title="AGI Tutor", page_icon="🧠", layout="wide")

# -------------------- styles --------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@600;800&display=swap');

html, body, [class*="st-"] { font-family: Nunito, system-ui, -apple-system, Segoe UI, Arial, sans-serif; }
body { background: #0f1220; color: #e9ecf1; }
.block-container { max-width: 1180px; padding-top: 10px; padding-bottom: 0; }

/* header */
.header {
  background: #151a2c;
  border: 1px solid #2b3250;
  border-radius: 16px;
  padding: 12px 16px;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 14px;
  align-items: center;
}
.title { font-size: 34px; font-weight: 800; color: #ffa733; margin: 0; }
.subtitle { margin: 0; opacity: .9; }

/* app shell: first row avatar+first bubble, second row scroll area, third row progress+input */
.shell {
  margin-top: 10px;
  background: #101528;
  border: 1px solid #2b3250;
  border-radius: 16px;
  padding: 12px;
  height: calc(100vh - 210px);
  display: grid;
  grid-template-rows: auto 1fr auto;
  gap: 12px;
}

/* first row grid */
.firstRow {
  display: grid;
  grid-template-columns: 280px 1fr;
  gap: 16px;
  align-items: start;
}

/* avatar card */
.avatarCard {
  background: #151a2c;
  border: 1px solid #2b3250;
  border-radius: 16px;
  padding: 10px;
}
.avatarCard img {
  width: 100%;
  max-height: 260px;
  object-fit: cover;
  border-radius: 12px;
  display: block;
}

/* message bubbles */
.messages {
  background: #12182d;
  border: 1px solid #2b3250;
  border-radius: 14px;
  padding: 12px;
  overflow: auto;
}
.bubble {
  border-radius: 14px;
  padding: 12px 14px;
  line-height: 1.55;
  margin-bottom: 10px;
  border: 1px solid #2b3250;
}
.bubble .who { font-weight: 800; opacity: .95; display: inline-block; margin-bottom: 6px; }
.tutor { background: #394058; }
.user  { background: #1f2a3c; }

/* small bits */
.metaRow { font-size: .95rem; opacity: .9; }
.badge { background:#1e233d; border:1px solid #3b4166; border-radius: 10px; padding:4px 8px; display:inline-block; margin:4px 6px 0 0; }
.block-container .stProgress { margin-top: 4px; }
.sidebar-section { margin-bottom: 14px; }
</style>
""", unsafe_allow_html=True)

# -------------------- data --------------------
users = fetchall("SELECT id, name FROM users ORDER BY name")
if not users:
    st.error("No users found. Add a user with the CLI and reload.")
    st.stop()

# session state defaults
ss = st.session_state
for k, v in {
    "session_active": False,
    "booted": False,
    "messages": [],
    "session_id": None,
    "correct_streak": 0,
    "consecutive_ready": 0,
    "topic": None,
    "show_last": 7,
}.items():
    if k not in ss:
        ss[k] = v

# -------------------- sidebar --------------------
with st.sidebar:
    st.markdown("### Learner")
    sel_name = st.selectbox(" ", [u["name"] for u in users], index=0, label_visibility="collapsed")
    st.markdown("<div class='sidebar-section'></div>", unsafe_allow_html=True)

    ss.show_last = st.slider("Show last messages", 1, 12, ss.show_last)
    st.markdown("<div class='sidebar-section'></div>", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.button("▶️ Start session", disabled=ss.session_active, use_container_width=True, key="start_btn")
    with c2:
        st.button("⏹ End session", disabled=not ss.session_active, use_container_width=True, key="end_btn")

    st.markdown("#### Badges")
    earned = fetchall(
        "SELECT badge, earned_at FROM badges "
        "WHERE user_id=(SELECT id FROM users WHERE name=?) ORDER BY id DESC",
        (sel_name,),
    )
    if earned:
        for row in earned[:6]:
            when = row["earned_at"].split("T")[0] if row["earned_at"] else ""
            st.markdown(f"<span class='badge'>{row['badge']} · {when}</span>", unsafe_allow_html=True)

# reflect sidebar button clicks
if st.session_state.get("start_btn"):
    ss.session_active = True
    ss.booted = False
    ss.messages = []
    ss.correct_streak = 0
    ss.consecutive_ready = 0

if st.session_state.get("end_btn"):
    if ss.session_id:
        execute("UPDATE sessions SET ended_at=? WHERE id=?", (datetime.utcnow().isoformat(timespec="seconds"), ss.session_id))
    ss.session_active = False

user = fetchone("SELECT * FROM users WHERE name=?", (sel_name,))
assert user, "Selected user missing"

# -------------------- header --------------------
st.markdown(f"""
<div class="header">
  <div>
    <div class="title">Maths Tutor</div>
    <p class="subtitle">Your interactive AI tutor, friendly and adaptable</p>
  </div>
  <div style="text-align:right;">{sel_name}</div>
</div>
""", unsafe_allow_html=True)

# helpers
def blend_conf(model_conf: float, streak: int) -> float:
    observed = min(1.0, 0.50 + 0.20*(1 if streak>0 else 0) + 0.10*max(0, streak-1))
    return MODEL_CONF_WEIGHT*model_conf + (1-MODEL_CONF_WEIGHT)*observed

def _avatar_img_tag() -> str:
    """Return an <img> tag with a base64 data URI, so it lives inside our firstRow HTML."""
    avatar_path = Path("ui/assets/tutor_character.png")
    if avatar_path.exists():
        data = avatar_path.read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        return f'<img alt="Tutor avatar" src="data:image/png;base64,{b64}"/>'
    return '<div style="font-size:72px; text-align:center;">🧑‍🚀</div>'

# -------------------- first tutor turn --------------------
if ss.session_active and not ss.booted:
    ss.topic = next_topic_for(user["id"]) or "Number and Algebra"

    context = {
        "student": {"name": user["name"], "stage": user["stage"], "region": user["region"]},
        "time": {"sessions_per_week": user["sessions_per_week"], "hours_per_session": user["hours_per_session"], "school_year_end": user["school_year_end"]},
        "curriculum_topic": ss.topic,
    }
    system_prompt = build_system_prompt(context)
    ss.messages.append({"role": "system", "content": system_prompt})
    ss.messages.append({"role": "system", "content": STRICT_RULES})  # <-- NEW strict rule
    ss.messages.append({"role": "user", "content": f"Start the session now for {user['name']}. Greet the learner, set the goal, ask a first question."})

    sid = execute("INSERT INTO sessions(user_id, topic, started_at) VALUES(?,?,?)",
                  (user["id"], ss.topic, datetime.utcnow().isoformat(timespec="seconds")))
    ss.session_id = sid

    tutor_text = call_model(ss.messages)
    text, assess = split_assessment(tutor_text)
    if not assess:
        assess = recover_assessment(ss.messages, tutor_text)

    ss.messages.append({"role": "assistant", "content": tutor_text})
    ss.booted = True

    mc = float(assess.get("confidence", 0.0)) if isinstance(assess, dict) else 0.0
    me = float(assess.get("mastery_estimate", 0.0)) if isinstance(assess, dict) else 0.0
    was_correct = bool(assess.get("last_response_correct", False)) if isinstance(assess, dict) else False

    ss.correct_streak = (ss.correct_streak + 1) if was_correct else 0
    bc = blend_conf(mc, ss.correct_streak)

    execute("UPDATE sessions SET mastery_estimate=?, confidence=? WHERE id=?", (me, bc, ss.session_id))
    execute(
        "INSERT INTO progress(user_id, topic, mastery, updated_at) VALUES(?,?,?,?) "
        "ON CONFLICT(user_id, topic) DO UPDATE SET mastery=excluded.mastery, updated_at=excluded.updated_at",
        (user["id"], ss.topic, me, datetime.utcnow().isoformat(timespec="seconds"))
    )

# -------------------- main panel --------------------
if ss.session_active:
    st.markdown("<div class='shell'>", unsafe_allow_html=True)

    # messages excluding system bootstrap
    visible_all = [m for i, m in enumerate(ss.messages) if i not in (0, 1, 2)]  # skip two system + strict rules
    first_idx = next((i for i, m in enumerate(visible_all) if m["role"] == "assistant"), -1)
    first_assistant = visible_all[first_idx] if first_idx != -1 else None

    # FIRST ROW: avatar + first tutor bubble
    first_txt = "Waiting for tutor…"
    if first_assistant is not None:
        first_txt, _ = split_assessment(first_assistant["content"])
    first_txt = first_txt.replace("\n", "<br>")

    first_row_html = f"""
    <div class="firstRow">
      <div class="avatarCard">{_avatar_img_tag()}</div>
      <div>
        <div class="bubble tutor"><span class="who">🧑‍🚀 Tutor</span><br>{first_txt}</div>
      </div>
    </div>
    """
    st.markdown(first_row_html, unsafe_allow_html=True)

    # SECOND ROW: tail messages
    tail = visible_all[first_idx + 1:] if first_idx != -1 else []
    N = int(getattr(ss, "show_last", 7))
    if len(tail) > N:
        tail = tail[-N:]

    bubbles = []
    for msg in tail:
        if msg["role"] == "assistant":
            text, _ = split_assessment(msg["content"])
            bubbles.append(f"<div class='bubble tutor'><span class='who'>🧑‍🚀 Tutor</span><br>{text.replace(chr(10), '<br>')}</div>")
        elif msg["role"] == "user":
            bubbles.append(f"<div class='bubble user'><span class='who'>👤 You</span><br>{msg['content'].replace(chr(10), '<br>')}</div>")
    st.markdown(f"<div class='messages'>{''.join(bubbles)}</div>", unsafe_allow_html=True)

    # THIRD ROW: progress + chat input
    last = fetchone("SELECT mastery_estimate, confidence FROM sessions WHERE id=?", (ss.session_id,))
    mastery_val = (last["mastery_estimate"] or 0.0) if last else 0.0
    conf_val = (last["confidence"] or 0.0) if last else 0.0

    st.markdown(f"<div class='metaRow'><b>Focus</b>, {ss.topic}</div>", unsafe_allow_html=True)
    st.progress(min(1.0, mastery_val))
    st.caption(f"Mastery, {mastery_val*100:.0f}%   Confidence, {conf_val*100:.0f}%   Streak, {ss.correct_streak}")

    answer = st.chat_input("Type your answer or question")
    if answer:
        ss.messages.append({"role": "user", "content": answer})
        st.rerun()

    # ---------------- tutor reply path (with pre-model autograde) ----------------
    if ss.messages and ss.messages[-1]["role"] == "user" and ss.booted:
        # find the last assistant message (the question we are answering)
        last_q_text = None
        for m in reversed(ss.messages[:-1]):
            if m["role"] == "assistant":
                last_q_text, _ = split_assessment(m["content"])
                break

        # Try deterministic grading first (range problems)
        grade = autograde(last_q_text, ss.messages[-1]["content"]) if last_q_text else None
        if grade and grade.get("task") == "range" and grade.get("correct"):
            # learner is correct – craft a brief confirmation reply, then update metrics
            rng = int(grade["expected"]) if float(grade["expected"]).is_integer() else grade["expected"]
            mn = int(grade["details"]["min"]) if float(grade["details"]["min"]).is_integer() else grade["details"]["min"]
            mx = int(grade["details"]["max"]) if float(grade["details"]["max"]).is_integer() else grade["details"]["max"]

            reply_text = (
                f"Brilliant, Archie, that’s correct. The range is {rng} because the largest number is {mx} "
                f"and the smallest is {mn}, and {mx} − {mn} = {rng}. "
                f"Ready for the next one?"
            )
            ss.messages.append({"role": "assistant", "content": reply_text})

            # update mastery/confidence in DB with a friendly boost
            last_row = fetchone("SELECT mastery_estimate, confidence FROM sessions WHERE id=?", (ss.session_id,))
            base_m = (last_row["mastery_estimate"] or 0.0) if last_row else 0.0
            me = min(1.0, base_m + 0.08)
            model_conf = 0.85
            ss.correct_streak += 1
            bc = blend_conf(model_conf, ss.correct_streak)

            execute("UPDATE sessions SET mastery_estimate=?, confidence=? WHERE id=?", (me, bc, ss.session_id))
            execute(
                "INSERT INTO progress(user_id, topic, mastery, updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id, topic) DO UPDATE SET mastery=excluded.mastery, updated_at=excluded.updated_at",
                (user["id"], ss.topic, me, datetime.utcnow().isoformat(timespec="seconds"))
            )

            st.rerun()

        # otherwise, fall back to the model as before
        reply = call_model(ss.messages)
        text, assess = split_assessment(reply)
        if not assess:
            assess = recover_assessment(ss.messages, reply)
        ss.messages.append({"role": "assistant", "content": reply})

        mc = float(assess.get("confidence", 0.0)) if isinstance(assess, dict) else 0.0
        me = float(assess.get("mastery_estimate", 0.0)) if isinstance(assess, dict) else 0.0
        correct = bool(assess.get("last_response_correct", False)) if isinstance(assess, dict) else False
        ready = bool(assess.get("ready_to_advance", False)) if isinstance(assess, dict) else False

        ss.correct_streak = (ss.correct_streak + 1) if correct else 0
        bc = blend_conf(mc, ss.correct_streak)

        execute("UPDATE sessions SET mastery_estimate=?, confidence=? WHERE id=?", (me, bc, ss.session_id))
        execute(
            "INSERT INTO progress(user_id, topic, mastery, updated_at) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id, topic) DO UPDATE SET mastery=excluded.mastery, updated_at=excluded.updated_at",
            (user["id"], ss.topic, me, datetime.utcnow().isoformat(timespec="seconds"))
        )

        execute("""CREATE TABLE IF NOT EXISTS badges(
            id INTEGER PRIMARY KEY,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            badge TEXT NOT NULL,
            earned_at TEXT NOT NULL,
            UNIQUE(user_id, topic, badge)
        )""")
        if me >= MASTERY_TARGET:
            try:
                execute("INSERT INTO badges(user_id, topic, badge, earned_at) VALUES(?,?,?,?)",
                        (user["id"], ss.topic, f"{ss.topic} • Mastery Star 🌟", datetime.utcnow().isoformat(timespec="seconds")))
            except Exception:
                pass

        if ready and me >= MASTERY_TARGET and ss.correct_streak >= 2:
            ss.consecutive_ready += 1
        else:
            ss.consecutive_ready = 0
        if ss.consecutive_ready >= 2:
            st.success("Great work, you have shown secure understanding. We can move on next time.")
            if ss.session_id:
                execute("UPDATE sessions SET ended_at=? WHERE id=?", (datetime.utcnow().isoformat(timespec="seconds"), ss.session_id))
            ss.session_active = False

        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)  # /shell

else:
    st.info("Click **Start session** to begin.")

# --- minimal visual overrides from your version ---
st.markdown("""
<style>
.shell{ background: transparent !important; border: 0 !important; border-radius: 0 !important; padding: 0 !important; margin-top: 0 !important; box-shadow: none !important; }
.messages{ border: 0 !important; }
.shell{ display: contents !important; height: auto !important; padding: 0 !important; margin: 0 !important; border: 0 !important; background: transparent !important; box-shadow: none !important; }
.messages{ max-height: calc(100vh - 360px) !important; overflow: auto !important; }
</style>
""", unsafe_allow_html=True)
