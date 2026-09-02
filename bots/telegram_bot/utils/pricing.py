"""
Canonical Pricing Utility for PFAST_AI.

Provides deterministic parsing, normalization, and display formatting
for subscription plan prices throughout the application.
"""

import re
from typing import Any, Optional, Tuple


def parse_price_value(value: Any) -> Optional[int]:
    """
    Parses a raw price input into a clean integer value.
    Handles Persian/English digits, emojis, commas, slashes, and unit multipliers.

    Examples:
        "200/000 💸" -> 200000
        "200,000"     -> 200000
        "200000"      -> 200000
        "۲۰۰/۰۰۰"     -> 200000
        "1/500/000"   -> 1500000
        "350 هزار"    -> 350000
        "1.5 میلیون"  -> 1500000
        "200k"        -> 200000
    """
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return int(value)

    text = str(value).strip()
    if not text:
        return None

    # 1. Normalize Persian/Arabic digits to ASCII 0-9
    text = text.translate(
        str.maketrans(
            "۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩",
            "01234567890123456789",
        )
    )

    # 2. Normalize decimal points and remove commas
    text = (
        text
        .replace("٫", ".")
        .replace("٬", "")
        .replace("،", "")
        .replace(",", "")
    )

    # 3. Normalize slash thousands separators (e.g. 200/000 -> 200000, 1/500/000 -> 1500000)
    # Loop while slash between digits exists to handle multiple slashes like 1/500/000
    while re.search(r"(\d)\s*/\s*(\d)", text):
        text = re.sub(r"(\d)\s*/\s*(\d)", r"\1\2", text)

    # 4. Remove emojis and special non-alphanumeric/unit characters (keep dots, letters, words)
    text = re.sub(r"[^\w\s.-]", " ", text)

    tokens = [token for token in re.split(r"\s+", text) if token]
    if not tokens:
        return None

    units = {
        "هزار": 1000,
        "k": 1000,
        "thousand": 1000,
        "میلیون": 1_000_000,
        "m": 1_000_000,
        "million": 1_000_000,
        "میلیارد": 1_000_000_000,
        "b": 1_000_000_000,
        "billion": 1_000_000_000,
    }

    currencies = {
        "تومان",
        "toman",
        "t",
        "rial",
        "irr",
        "ریال",
    }

    number: Optional[float] = None

    for token in tokens:
        lower = token.lower()

        if lower in currencies:
            continue

        if lower in units:
            if number is not None:
                number = number * units[lower]
            continue

        # Match number with optional attached unit suffix (e.g. 200k, 1.5m)
        match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([^0-9\s.]+)?", token)
        if match:
            num_str = match.group(1)
            suffix = (match.group(2) or "").lower()

            try:
                parsed_float = float(num_str)
            except ValueError:
                continue

            multiplier = units.get(suffix, 1)
            parsed = parsed_float * multiplier

            if number is None:
                number = parsed
            else:
                if multiplier == 1 and "." not in num_str and "." not in str(number):
                    number = float(f"{int(number)}{int(parsed)}")
                else:
                    number = number * multiplier
            continue

        try:
            parsed_float = float(token)
            if number is None:
                number = parsed_float
            else:
                number = float(f"{int(number)}{int(parsed_float)}")
        except ValueError:
            continue

    if number is None:
        return None

    return int(round(number))


def parse_price_input(text: str) -> Tuple[int, str]:
    """
    Parses a user or admin price input text and extracts (amount, currency).
    Defaults to 'تومان' unless explicitly specified as 'IRR'/'ریال'.
    """
    amount = parse_price_value(text)
    if amount is None:
        raise ValueError("Invalid price value")

    lowered = str(text or "").lower()

    if any(marker in lowered for marker in ("ریال", "rial", "irr")):
        currency = "IRR"
    else:
        currency = "تومان"

    return amount, currency


def format_price(
    amount: Any,
    currency: Optional[str] = "تومان",
    include_currency: bool = True,
) -> str:
    """
    Formats a numeric price with '/' as the canonical thousands separator.
    Examples:
        200000 -> "200/000 تومان"
        1500000 -> "1/500/000 تومان"
        10000000 -> "10/000/000 تومان"
        200000, include_currency=False -> "200/000"
    """
    try:
        numeric = int(amount or 0)
    except (ValueError, TypeError):
        numeric = 0

    formatted_num = f"{numeric:,}".replace(",", "/")

    if include_currency and currency:
        return f"{formatted_num} {currency}".strip()
    return formatted_num