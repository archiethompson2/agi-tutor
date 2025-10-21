from __future__ import annotations
import json
import re
from typing import Dict, List, Tuple
from openai import OpenAI
from .config import settings

ASSESSMENT_START = "[[ASSESSMENT]]"
ASSESSMENT_END = "[[/ASSESSMENT]]"

client = OpenAI(api_key=settings.openai_api_key)

from __future__ import annotations

def build_system_prompt(context: dict) -> str:
    """Build the tutor system prompt from structured context.
    Enforces a strict, repeatable tutoring turn format so the chat stays cohesive.
    """
    student = context.get("student", {})
    time = context.get("time", {})
    topic = context.get("curriculum_topic", "Maths")
    must_cover = context.get("must_cover") or []

    lines = []
    lines.append("You are a warm, encouraging maths tutor. Use very clear, step-by-step explanations, tiny increments, and quick checks.")
    lines.append(f"Learner: {student.get('name','Learner')}. Region: {student.get('region','')}. Stage: {student.get('stage','')}.")
    if time:
        lines.append(f"Schedule → sessions/week: {time.get('sessions_per_week','?')}, hours/session: {time.get('hours_per_session','?')}, school year end: {time.get('school_year_end','?')}.")

    lines.append(f"Today’s focus: {topic}.")

    if must_cover:
        lines.append("You must cover these items, in order, and tick them off as the learner demonstrates success:")
        for i, item in enumerate(must_cover, 1):
            obj = item.get("objective", "")
            sc = item.get("success_criteria", "")
            if sc:
                lines.append(f"{i}. {obj} — success criteria: {sc}")
            else:
                lines.append(f"{i}. {obj}")

    lines.append(
        """
TUTORING TURN FORMAT (use this every turn):
1) ONE-SENTENCE RECAP of the learner’s last message in your own words.
2) MICRO-EXPLANATION (2–4 short sentences) focused on the exact next step only.
3) SINGLE PROMPTED ACTION: ask exactly ONE clear question or instruction.
   - If they struggled last turn, offer a hint with smaller numbers or a scaffold.
   - Prefer number lines, bar models, or quick mental checks.
4) [[ASSESSMENT]] JSON with keys:
   {"last_response_correct": <true|false|null>,
    "mastery_estimate": <0..1>,
    "confidence": <0..1>,
    "ready_to_advance": <true|false>}
Wrap the JSON exactly in [[ASSESSMENT]] ... [[/ASSESSMENT]].
        """.strip()
    )

    lines.append("Keep language friendly and concise. Never ask multiple questions at once. Always end with exactly one question.")
    return "\n".join(lines)
        "You are a warm, encouraging Year 8 maths tutor in Wales. "
        "Use a calm tone, praise effort, keep questions short. "
        "If the learner is unsure or incorrect, respond kindly, teach the smallest missing step, "
        "give one similar practice item, and stay on the micro skill until it is secure. "
        "Avoid long dashes, avoid Oxford commas, use clear UK English. "
        "Ask one question at a time.\n\n"
        "Confidence policy:\n"
        "- confidence measures how sure YOU are about your mastery estimate right now.\n"
        "- Base confidence on the clarity of your reasoning, consistency over the last few turns, "
        "and whether you can explain the step simply.\n"
        "- If the learner just answered correctly after a previous erro