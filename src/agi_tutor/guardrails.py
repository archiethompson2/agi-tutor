import re
from typing import Optional, Dict

_num = re.compile(r"-?\d+(?:\.\d+)?")

def _numbers(text: str):
    return [float(x) for x in _num.findall(text or "")]

def autograde(question_text: str, answer_text: str) -> Optional[Dict]:
    """
    Returns dict with keys: task, correct, expected, student, details
    or None if we do not recognise the question.
    Currently supports 'range' problems like:
      "What is the range of 3, 7, 7, 10?"
    """
    if not question_text:
        return None
    ql = question_text.lower()
    if "range" in ql:
        nums = _numbers(question_text)
        if len(nums) >= 2:
            mn, mx = min(nums), max(nums)
            expected = mx - mn
            ans_nums = _numbers(answer_text)
            student = ans_nums[0] if ans_nums else None
            correct = (student is not None) and abs(student - expected) < 1e-9
            return {
                "task": "range",
                "correct": bool(correct),
                "expected": expected,
                "student": student,
                "details": {"min": mn, "max": mx},
            }
    return None
