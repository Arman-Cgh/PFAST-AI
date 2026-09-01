"""
Core Password Security Service.

Pure deterministic business logic for cryptographically secure password
generation and local password strength/entropy analysis.

Security & Privacy Guarantees:
- Zero network or external AI requests.
- Zero database interactions or disk persistence.
- Zero logging of raw passwords or generated outputs.
- Passwords exist transiently in memory only during analysis.
"""

import math
import re
import secrets
import string
from typing import Any, Dict, List, Optional, Set


DEFAULT_SYMBOLS = "!@#$%^&*()_+-=[]{}|;:,.<>?"

# Curated set of common/vulnerable passwords (normalized lowercase)
COMMON_WEAK_PASSWORDS: Set[str] = {
    "password", "password123", "pass123", "p@ssword", "p@ssw0rd", "pass@123",
    "123456", "12345678", "123456789", "12345", "1234567", "1234567890",
    "qwerty", "qwerty123", "qwertyuiop", "asdfgh", "asdfghjkl", "zxcvbnm",
    "admin", "admin123", "administrator", "root", "toor", "default",
    "welcome", "welcome123", "iloveyou", "princess", "dragon", "master",
    "monkey", "shadow", "football", "baseball", "superman", "charlie",
    "donald", "letmein", "sunshine", "starwars", "secret", "login",
    "test1234", "trustno1", "guest", "changeme", "mypolice", "abc123",
}

# Sequential string maps for detection
SEQUENTIAL_MAPS: List[str] = [
    string.digits,               # 0123456789
    string.digits[::-1],         # 9876543210
    string.ascii_lowercase,      # abcdefghijklmnopqrstuvwxyz
    string.ascii_lowercase[::-1],# zyxwvutsrqponmlkjihgfedcba
]

# Keyboard spatial walk patterns
KEYBOARD_PATTERNS: List[str] = [
    "qwertyuiop",
    "poiuytrewq",
    "asdfghjkl",
    "lkjhgfdsa",
    "zxcvbnm",
    "mnbvcxz",
    "1qaz2wsx3edc4rfv5tgb6yhn7ujm8ik9ol0p",
    "qazwsxedcrfvtgbyhnujmikolp",
]

LEET_MAP: Dict[str, str] = {
    "@": "a",
    "4": "a",
    "8": "b",
    "3": "e",
    "!": "i",
    "|": "i",
    "0": "o",
    "5": "s",
    "$": "s",
    "7": "t",
    "+": "t",
}


def _normalize_leetspeak(text: str) -> str:
    """Normalize common leetspeak substitutions to lowercase letters."""
    chars = [LEET_MAP.get(c, c) for c in text.lower()]
    return "".join(chars)


def _find_common_word(text: str) -> Optional[str]:
    """Check if the text matches or contains any common vulnerable passwords/roots."""
    text_lower = text.lower()
    leet_text = _normalize_leetspeak(text)

    if text_lower in COMMON_WEAK_PASSWORDS:
        return text_lower

    if leet_text in COMMON_WEAK_PASSWORDS:
        return leet_text

    for word in COMMON_WEAK_PASSWORDS:
        if len(word) >= 4 and (word in text_lower or word in leet_text):
            return word

    return None


def generate_secure_password(
    length: int = 16,
    include_uppercase: bool = True,
    include_lowercase: bool = True,
    include_digits: bool = True,
    include_symbols: bool = True,
    custom_symbols: str = DEFAULT_SYMBOLS,
) -> str:
    """
    Generate a cryptographically secure password using Python's secrets module.

    Guarantees at least one character from each active character group,
    and shuffles the resulting characters securely with Fisher-Yates.
    """
    if not isinstance(length, int) or length < 4:
        raise ValueError("Password length must be an integer of at least 4.")

    if length > 128:
        raise ValueError("Password length cannot exceed 128 characters.")

    pools: List[str] = []
    if include_uppercase:
        pools.append(string.ascii_uppercase)
    if include_lowercase:
        pools.append(string.ascii_lowercase)
    if include_digits:
        pools.append(string.digits)
    if include_symbols:
        symbols = str(custom_symbols or DEFAULT_SYMBOLS)
        if not symbols:
            symbols = DEFAULT_SYMBOLS
        pools.append(symbols)

    if not pools:
        raise ValueError("At least one character group must be selected.")

    if length < len(pools):
        raise ValueError(
            f"Length {length} is too short to include all {len(pools)} selected character groups."
        )

    # 1. Pick at least one character from each selected pool
    password_chars = [secrets.choice(pool) for pool in pools]

    # 2. Fill the rest of the password from the combined pool
    all_chars = "".join(pools)
    remaining_length = length - len(password_chars)
    for _ in range(remaining_length):
        password_chars.append(secrets.choice(all_chars))

    # 3. Secure in-place Fisher-Yates shuffle
    for i in range(len(password_chars) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        password_chars[i], password_chars[j] = password_chars[j], password_chars[i]

    return "".join(password_chars)


def _check_sequential_patterns(text: str, min_len: int = 3) -> bool:
    """Check if the text contains sequential alphanumeric runs of length >= min_len."""
    text_lower = text.lower()
    for seq in SEQUENTIAL_MAPS:
        for i in range(len(seq) - min_len + 1):
            chunk = seq[i : i + min_len]
            if chunk in text_lower:
                return True
    return False


def _check_keyboard_patterns(text: str, min_len: int = 3) -> bool:
    """Check if the text contains keyboard walk runs of length >= min_len."""
    text_lower = text.lower()
    for pattern in KEYBOARD_PATTERNS:
        for i in range(len(pattern) - min_len + 1):
            chunk = pattern[i : i + min_len]
            if chunk in text_lower:
                return True
    return False


def _check_repeated_chars(text: str, threshold: int = 3) -> bool:
    """Check if any character is consecutively repeated threshold+ times (e.g. 'aaaa')."""
    if not text:
        return False
    count = 1
    for i in range(1, len(text)):
        if text[i] == text[i - 1]:
            count += 1
            if count >= threshold:
                return True
        else:
            count = 1
    return False


def _check_repeated_substrings(text: str, min_sub_len: int = 2) -> bool:
    """Check if the text consists of repeating sequences (e.g. 'abcabc', '121212')."""
    n = len(text)
    if n < min_sub_len * 2:
        return False

    for sub_len in range(min_sub_len, (n // 2) + 1):
        for i in range(n - (sub_len * 2) + 1):
            sub1 = text[i : i + sub_len]
            sub2 = text[i + sub_len : i + (sub_len * 2)]
            if sub1.lower() == sub2.lower():
                return True
    return False


def analyze_password_strength(password: str) -> Dict[str, Any]:
    """
    Perform local, deterministic security and entropy analysis on a password.

    Evaluates:
    - Length & character diversity
    - Shannon character-pool entropy
    - Common weak passwords (exact & leetspeak)
    - Sequential and keyboard walk patterns
    - Repeated characters and substrings

    Returns structured analysis with actionable feedback.
    """
    if password is None:
        password = ""

    length = len(password)
    issues: List[str] = []
    feedback: List[str] = []

    if length == 0:
        return {
            "strength": "very_weak",
            "score": 0,
            "estimated_entropy": 0.0,
            "length": 0,
            "issues": ["empty_password"],
            "feedback": ["رمز عبور نمی‌تواند خالی باشد."],
        }

    # 1. Character diversity analysis
    has_lower = bool(re.search(r"[a-z]", password))
    has_upper = bool(re.search(r"[A-Z]", password))
    has_digits = bool(re.search(r"\d", password))
    has_symbols = bool(re.search(r"[^a-zA-Z0-9\s]", password))

    pool_size = 0
    if has_lower:
        pool_size += 26
    if has_upper:
        pool_size += 26
    if has_digits:
        pool_size += 10
    if has_symbols:
        pool_size += 32

    # Estimated Shannon entropy (informational metric)
    estimated_entropy = 0.0
    if pool_size > 0:
        estimated_entropy = round(length * math.log2(pool_size), 2)

    # 2. Base score from length
    score = 0
    if length < 6:
        score += 5
        issues.append("too_short")
        feedback.append("طول رمز عبور بسیار کوتاه و ناامن است (حداقل ۱۲ کاراکتر توصیه می‌شود).")
    elif 6 <= length <= 8:
        score += 15
        issues.append("short_length")
        feedback.append("طول رمز عبور کوتاه است؛ ترجیحاً از ۱۲ کاراکتر یا بیشتر استفاده کنید.")
    elif 9 <= length <= 11:
        score += 30
    elif 12 <= length <= 15:
        score += 45
    else:
        score += 55

    # 3. Variety score
    variety_count = sum([has_lower, has_upper, has_digits, has_symbols])
    if variety_count == 1:
        score += 5
        issues.append("single_character_type")
        feedback.append("فقط از یک نوع کاراکتر استفاده شده است. از ترکیب حروف کوچک، بزرگ، اعداد و نمادها استفاده کنید.")
    elif variety_count == 2:
        score += 15
        issues.append("low_variety")
        feedback.append("تنوع کاراکترها کم است. افزودن نمادها یا حروف بزرگ امنیت را بالا می‌برد.")
    elif variety_count == 3:
        score += 25
    elif variety_count == 4:
        score += 35

    if not has_upper:
        feedback.append("افزودن حروف بزرگ انگلیسی (A-Z) قدرت رمز را تقویت می‌کند.")
    if not has_digits:
        feedback.append("افزودن اعداد (0-9) پیچیدگی رمز را افزایش می‌دهد.")
    if not has_symbols:
        feedback.append("استفاده از نمادها مانند !@#$% رمز را در برابر حملات Brute-Force مقاوم می‌کند.")

    # 4. Pattern penalties
    matched_common = _find_common_word(password)
    is_common = matched_common is not None
    if is_common:
        score = min(score, 15)
        score -= 40
        issues.append("common_weak_password")
        feedback.append("این رمز عبور بسیار شناخته‌شده یا رایج است و در بانک‌های اطلاعاتی نشت داده قرار دارد.")

    # Check sequential patterns
    if _check_sequential_patterns(password, min_len=3):
        score -= 15
        issues.append("sequential_pattern")
        feedback.append("از توالی‌های پشت سر هم مثل 123 یا abc خودداری کنید.")

    # Check keyboard patterns
    if _check_keyboard_patterns(password, min_len=3):
        score -= 15
        issues.append("keyboard_walk_pattern")
        feedback.append("الگوهای خطی کیبورد (مانند qwerty یا asdf) به راحتی قابل پیش‌بینی هستند.")

    # Check repeated characters
    if _check_repeated_chars(password, threshold=3):
        score -= 15
        issues.append("repeated_characters")
        feedback.append("تکرار پشت سر هم یک کاراکتر (مانند aaa یا 111) از استحکام رمز می‌کاهد.")

    # Check repeated sequences
    if _check_repeated_substrings(password, min_sub_len=2):
        score -= 15
        issues.append("repeated_substring")
        feedback.append("تکرار عبارت‌ها (مانند passpass) امنیت رمز را تضعیف می‌کند.")

    # Length < 8 additional penalty
    if length < 8:
        score -= 15

    # Clamp score 0 to 100
    final_score = max(0, min(100, score))

    # 5. Strength level classification
    if is_common or final_score < 25:
        strength = "very_weak"
    elif 25 <= final_score < 50:
        strength = "weak"
    elif 50 <= final_score < 70:
        strength = "medium"
    elif 70 <= final_score < 85:
        strength = "strong"
    else:
        strength = "very_strong"

    if not feedback:
        feedback.append("رمز عبور از طول و تنوع بسیار مناسبی برخوردار است.")

    return {
        "strength": strength,
        "score": final_score,
        "estimated_entropy": estimated_entropy,
        "length": length,
        "issues": issues,
        "feedback": feedback,
    }
