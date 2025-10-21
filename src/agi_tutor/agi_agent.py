from __future__ import annotations

import json, re
from typing import Dict, List, Tuple
from openai import OpenAI
from .config import settings

ASSESSMENT_START = "[[ASSESSMENT]]"
ASSESSMENT_END = "[[/ASSESSMENT]]"

# OpenAI client using your config
client = OpenAI(api_key=settings.openai_api_key)

def build_system_prompt(context: dict) -> str:
    """Build the tutor system prompt from structured context.
    Enforces a strict, repeatable tutoring turn format so the chat stays cohesive.
    """
    student = context.get("student", {})
    time = context.get("time", {})
    topic = context.get("curriculum_topic", "Maths")
    must_cover = context.get("must_cover") or []

    lines: List[str] = []
    lines.append("You are a warm, encouraging maths tutor. Use very clear, step-by-step explanations, tiny increments, and quick checks.")
    lines.append(f"Learner: {student.get('name','Learner')}. Region: {student.get('region','')}. Stage: {student.get('stage','')}.")
    if time:
        lines.append(
            f"Schedule → sessions/week: {time.get('sessions_per_week','?')}, "
            f"hours/session: {time.get('hours_per_session','?')}, "
            f"school year end: {time.get('school_year_end','?')}."
        )

    lines.append(f"Today’s focus: {topic}.")

    if must_cover:
        lines.append("You must cover these items, in order, and tick them off as the learner demonstrates success:")
        for i, item in enumerate(must_cover, 1):
            obj = item.get("objective", "")
            sc = item.get("success_criteria", "")
            lines.append(f"{i}. {obj}" + (f" — success criteria: {sc}" if sc else ""))

    lines.append(
        (
            "TUTORING TURN FORMAT (use this every turn):\n"
            "1) ONE-SENTENCE RECAP of the learner’s last message in your own words.\n"
            "2) MICRO-EXPLANATION (2–4 short sentences) focused on the exact next step only.\n"
            "3) SINGLE PROMPTED ACTION: ask exactly ONE clear question or instruction.\n"
            "   - If they struggled last turn, offer a hint with smaller numbers or a scaffold.\n"
            "   - Prefer number lines, bar models, or quick mental checks.\n"
            "4) [[ASSESSMENT]] JSON with keys:\n"
            "   {\"last_response_correct\": <true|false|null>,\n"
            "    \"mastery_estimate\": <0..1>,\n"
            "    \"confidence\": <0..1>,\n"
            "    \"ready_to_advance\": <true|false>}\n"
            "Wrap the JSON exactly in [[ASSESSMENT]] ... [[/ASSESSMENT]]."
        )
    )

    lines.append("
    # --- OVERRIDE: strict item-level assessment schema and advancement rule ---
    lines.append(
        (
            "OVERRIDE — Use this stricter tutoring format in EVERY turn (this supersedes earlier instructions):\n"
            "1) ONE-SENTENCE RECAP of the learner’s last message.\n"
            "2) MICRO-EXPLANATION (2–4 short sentences) for the exact next step.\n"
            "3) ONE ACTION ONLY: ask exactly one question/instruction. Scaffold if they struggled.\n"
            "4) [[ASSESSMENT]] JSON (STRICT):\n"
            "   {\"item_index\": <int zero-based>,\n"
            "    \"objective\": <string of the current item's objective>,\n"
            "    \"last_response_correct\": <true|false|null>,\n"
            "    \"mastery_estimate\": <0..1>,\n"
            "    \"confidence\": <0..1>,\n"
            "    \"ready_to_advance\": <true|false>,\n"
            "    \"needs_more_practice\": <true|false>}\n"
            "Rule: 0.70 is the secure threshold. If confidence < 0.70, stay on the SAME item and scaffold. "
            "If confidence ≥ 0.70 AND mastery_estimate ≥ 0.70, advance to the NEXT item.\n"
            "Wrap the JSON EXACTLY in [[ASSESSMENT]] ... [[/ASSESSMENT]]."
        )
    )

    Keep language friendly and concise. Never ask multiple questions at once. Always end with exactly one question.")
    return "\n".join(lines)

def call_model(messages: List[Dict], temperature: float = 0.2, max_tokens: int = 700) -> str:
    """Minimal wrapper for chat completions using configured model/key."""
    r = client.chat.completions.create(
        model=settings.openai_model,
        temperature=temperature,
        max_tokens=max_tokens,
        messages=messages,
    )
    return (r.choices[0].message.content or "").strip()

def split_assessment(text: str) -> Tuple[str, Dict]:
    """Remove and parse the [[ASSESSMENT]]...[[/ASSESSMENT]] block, return (text_without_block, assessment_dict)."""
    pattern = re.compile(re.escape(ASSESSMENT_START) + r"(.*?)" + re.escape(ASSESSMENT_END), re.DOTALL)
    m = pattern.search(text or "")
    assess: Dict = {}
    if m:
        try:
            assess = json.loads(m.group(1).strip())
        except Exception:
            assess = {}
        text = pattern.sub("", text).strip()
    return text, assess

def recover_assessment(messages: List[Dict], assistant_text: str) -> Dict:
    """Ask the model to output ONLY the assessment block if it was missing or malformed."""
    prompt = (
        "Return ONLY the assessment block for the last assistant turn, no other text. "
        f"Wrap strictly as {ASSESSMENT_START}" + "{...}" + f"{ASSESSMENT_END}. "
        "Keys required: item_index, objective, mastery_estimate, confidence, last_response_correct, ready_to_advance, needs_more_practice. (Do not include any other text.) Keys required: mastery_estimate, confidence, topic, focus_area, last_response_correct, "
        "ready_to_advance, ne