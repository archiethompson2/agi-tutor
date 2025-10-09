from __future__ import annotations

def build_system_prompt(context: dict) -> str:
    """
    Build the tutor system prompt from structured context.
    Supports optional context['must_cover'] = list of {'objective','success_criteria'}
    """
    student = context.get("student", {})
    time = context.get("time", {})
    topic = context.get("curriculum_topic", "Maths")
    must_cover = context.get("must_cover") or []

    lines = []
    lines.append("You are a warm, encouraging maths tutor. Use clear, step by step explanations and small checks.")
    lines.append(f"Learner name, {student.get('name','Learner')}. Region, {student.get('region','')}. Stage, {student.get('stage','')}.")
    if time:
        lines.append(f"Sessions per week, {time.get('sessions_per_week','?')}, hours per session, {time.get('hours_per_session','?')}, school year end, {time.get('school_year_end','?')}.")

    lines.append(f"Today’s focus, {topic}.")

    if must_cover:
        lines.append("You must cover these items in this session, prioritise them in the given order if time is short.")
        for i, item in enumerate(must_cover, 1):
            obj = item.get("objective", "")
            sc = item.get("success_criteria", "")
            if sc:
                lines.append(f"{i}. {obj} — success criteria, {sc}")
            else:
                lines.append(f"{i}. {obj}")

    lines.append("Be nurturing if they struggle, teach the exact gap, and only move on once the concept is secure.")
    lines.append("Always end with a single question to keep the dialogue going.")
    lines.append("At the end of each turn, include a machine readable assessment JSON block with fields last_response_correct, mastery_estimate, confidence, ready_to_advance.")
    return "\n".join(lines)
