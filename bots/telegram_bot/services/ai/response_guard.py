import re


BLOCKED_PATTERNS = [
    r"من\s+PF-AI\s+هستم.*",
    r"من\s+یک\s+دستیار\s+هوشمند\s+هستم.*",
    r"من\s+یک\s+هوش\s+مصنوعی\s+هستم.*",
    r"این\s+را\s+به\s+خاطر\s+دارم.*",
    r"به\s+خاطر\s+سپردم.*",
]


def clean_response(text: str):

    if not text:
        return text


    cleaned = text


    for pattern in BLOCKED_PATTERNS:

        cleaned = re.sub(
            pattern,
            "",
            cleaned,
            flags=re.IGNORECASE
        )


    cleaned = cleaned.strip()


    return cleaned