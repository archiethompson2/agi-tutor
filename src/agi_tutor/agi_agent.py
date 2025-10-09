from __future__ import annotations
import json
import re
from typing import Dict, List, Tuple
from openai import OpenAI
from .config import settings

ASSESSMENT_START = "[[ASSESSMENT]]"
ASSESSMENT_END = "[[/ASSESSMENT]]"

client = OpenAI(api_key=settings.openai_api_key)

def build_system_prompt(context: Dict) -> str:
    return (
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
        "- If the learner just answered correctly after a previous error, increase confidence slightly. "
        "If errors repeat, reduce it.\n\n"
        "At the end of every message append ONE single line JSON assessment wrapped by "
        f"{ASSESSMENT_START}{{...}}{ASSESSMENT_END} with keys:\n"
        "- mastery_estimate: float 0-1 for the current micro skill\n"
        "- confidence: float 0-1 for your certainty in that estimate\n"
        "- topic: string\n"
        "- focus_area: short string naming the exact micro skill or step\n"
        "- last_response_correct: boolean for the learner’s most recent answer\n"
        "- ready_to_advance: boolean becomes true only after two consecutive correct checks and mastery_estimate >= 0.85\n"
        "- needs_more_practice: boolean\n"
        "Only one assessment block per message.\n\n"
        "Context:\n" + json.dumps(context, ensure_ascii=False)
    )

def call_model(messages: List[Dict]) -> str:
    r = client.chat.completions.create(
        model=settings.openai_model,
        temperature=0.5,
        messages=messages,
    )
    return r.choices[0].message.content.strip()

def split_assessment(text: str) -> Tuple[str, Dict]:
    pattern = re.compile(re.escape(ASSESSMENT_START) + r"(.*?)" + re.escape(ASSESSMENT_END), re.DOTALL)
    m = pattern.search(text)
    assess = {}
    if m:
        try:
            assess = json.loads(m.group(1).strip())
        except Exception:
            assess = {}
        text = pattern.sub("", text).strip()
    return text, assess

def recover_assessment(messages: List[Dict], assistant_text: str) -> Dict:
    prompt = (
        "Return ONLY the assessment block for the last assistant turn, no other text. "
        f"Wrap strictly as {ASSESSMENT_START}{{...}}{ASSESSMENT_END}. "
        "Keys required: mastery_estimate, confidence, topic, focus_area, last_response_correct, "
        "ready_to_advance, needs_more_practice."
    )
    msgs = messages[:]
    msgs.append({"role": "assistant", "content": assistant_text})
    msgs.append({"role": "user", "content": prompt})
    try:
        txt = call_model(msgs)
        _, assess = split_assessment(txt)
        return assess if isinstance(assess, dict) else {}
    except Exception:
        return {}
