import re
from dataclasses import dataclass

from app import settings


@dataclass(frozen=True)
class Verdict:
    allowed: bool
    reason: str = ""
    sanitized_text: str = ""


_MASK_PATTERN = re.compile(r"\b(" + "|".join(map(re.escape, settings.MASKED_WORDS)) + r")\b", re.IGNORECASE)


def evaluate(text: str) -> Verdict:
    if not text.strip():
        return Verdict(False, "empty message")
    if len(text) > settings.MAX_MESSAGE_LENGTH:
        return Verdict(False, "message too long")
    lowered = text.lower()
    for term in settings.BLOCKED_TERMS:
        if term in lowered:
            return Verdict(False, f"blocked term: {term}")
    return Verdict(True, sanitized_text=_MASK_PATTERN.sub(lambda m: "*" * len(m.group(0)), text))
