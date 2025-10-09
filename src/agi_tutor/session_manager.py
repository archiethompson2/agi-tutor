from __future__ import annotations
from datetime import datetime
from typing import Dict, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .agi_agent import build_system_prompt, call_model, split_assessment, recover_assessment
from .db import execute
from .planner import next_topic_for

console = Console()

MASTERY_TARGET = 0.85
MODEL_CONF_WEIGHT = 0.6  # change to taste, higher means trust tutor more

def run_session(user_id: int, user_name: str, context: Dict, max_turns: int = 12) -> None:
    topic = next_topic_for(user_id) or context.get("curriculum_topic", "Number and Algebra")
    context["curriculum_topic"] = topic
    messages: List[Dict] = [
        {"role": "system", "content": build_system_prompt(context)},
        {"role": "user", "content": f"Start the session now for {user_name}. Greet the learner, set the goal, ask the first question."}
    ]
    session_id = execute(
        "INSERT INTO sessions(user_id, topic, started_at) VALUES(?,?,?)",
        (user_id, topic, datetime.utcnow().isoformat(timespec="seconds"))
    )

    consecutive_ready = 0
    correct_streak = 0  # observed signal

    try:
        for turn in range(max_turns):
            tutor = call_model(messages)
            text, assess = split_assessment(tutor)
            if not assess:
                assess = recover_assessment(messages, tutor)

            # Extract assessment fields
            focus_area = assess.get("focus_area") if isinstance(assess, dict) else None
            mastery = float(assess.get("mastery_estimate", 0.0)) if isinstance(assess, dict) else 0.0
            model_conf = float(assess.get("confidence", 0.0)) if isinstance(assess, dict) else 0.0
            last_correct = bool(assess.get("last_response_correct", False)) if isinstance(assess, dict) else False
            ready = bool(assess.get("ready_to_advance", False)) if isinstance(assess, dict) else False
            needs_practice = bool(assess.get("needs_more_practice", False)) if isinstance(assess, dict) else False

            # Update observed correctness streak
            correct_streak = (correct_streak + 1) if last_correct else 0

            # Observed confidence from behaviour, gentle ramp up with streak
            # 0.50 at baseline, +0.20 for first correct, +0.10 for each additional, capped at 1.0
            observed_conf = min(1.0, 0.50 + 0.20 * (1 if correct_streak > 0 else 0) + 0.10 * max(0, correct_streak - 1))

            # Blend model confidence with observed
            blended_conf = MODEL_CONF_WEIGHT * model_conf + (1 - MODEL_CONF_WEIGHT) * observed_conf

            # Show the tutor message
            console.print(Panel.fit(text, title=f"Tutor • {topic}"))

            # Status
            status = Table(show_header=True, header_style="bold")
            status.add_column("Focus")
            status.add_column("Mastery")
            status.add_column("Conf. model")
            status.add_column("Conf. observed")
            status.add_column("Conf. blended")
            status.add_column("Streak")
            status.add_row(focus_area or "—", f"{mastery:.2f}", f"{model_conf:.2f}", f"{observed_conf:.2f}", f"{blended_conf:.2f}", str(correct_streak))
            console.print(status)

            # Persist, store blended confidence
            execute("UPDATE sessions SET mastery_estimate=?, confidence=? WHERE id=?", (mastery, blended_conf, session_id))
            execute(
                "INSERT INTO progress(user_id, topic, mastery, updated_at) VALUES(?,?,?,?) "
                "ON CONFLICT(user_id, topic) DO UPDATE SET mastery=excluded.mastery, updated_at=excluded.updated_at",
                (user_id, topic, mastery, datetime.utcnow().isoformat(timespec="seconds"))
            )

            # Advancement gate
            if ready and mastery >= MASTERY_TARGET and correct_streak >= 2:
                consecutive_ready += 1
            else:
                consecutive_ready = 0

            if consecutive_ready >= 2:
                console.print(Panel.fit("Great work, you have shown secure understanding. We can move on next time.", title="Mastery reached"))
                break

            if needs_practice or mastery < MASTERY_TARGET:
                console.print("[dim]We will keep practising this small step until it feels easy.[/dim]")

            user = console.input("[bold green]You[/]: ")
            messages.append({"role": "assistant", "content": tutor})
            messages.append({"role": "user", "content": user})

            if user.strip().lower() in {"end", "quit", "exit"}:
                break

        execute("UPDATE sessions SET ended_at=? WHERE id=?", (datetime.utcnow().isoformat(timespec="seconds"), session_id))
    except KeyboardInterrupt:
        execute("UPDATE sessions SET ended_at=? WHERE id=?", (datetime.utcnow().isoformat(timespec="seconds"), session_id))
        console.print("\n[dim]Session ended.[/dim]")
