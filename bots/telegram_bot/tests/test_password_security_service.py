import re
import pytest

from services.security.password import (
    generate_secure_password,
    analyze_password_strength,
)


# ==============================================================================
# 1. Generator Tests
# ==============================================================================

def test_generate_password_default_length_and_groups():
    pwd = generate_secure_password()
    assert len(pwd) == 16
    assert any(c.isupper() for c in pwd)
    assert any(c.islower() for c in pwd)
    assert any(c.isdigit() for c in pwd)
    assert any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pwd)


def test_generate_password_custom_lengths():
    for length in [8, 12, 24, 32, 64]:
        pwd = generate_secure_password(length=length)
        assert len(pwd) == length


def test_generate_password_specific_groups_only():
    # Only digits and lowercase
    pwd = generate_secure_password(
        length=10,
        include_uppercase=False,
        include_lowercase=True,
        include_digits=True,
        include_symbols=False,
    )
    assert len(pwd) == 10
    assert not any(c.isupper() for c in pwd)
    assert not any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in pwd)
    assert any(c.islower() for c in pwd)
    assert any(c.isdigit() for c in pwd)


def test_generate_password_randomness():
    passwords = {generate_secure_password(length=16) for _ in range(50)}
    assert len(passwords) == 50  # All generated passwords must be unique


def test_generate_password_invalid_options():
    with pytest.raises(ValueError):
        generate_secure_password(length=3)  # too short

    with pytest.raises(ValueError):
        generate_secure_password(length=129)  # too long

    with pytest.raises(ValueError):
        # No group selected
        generate_secure_password(
            include_uppercase=False,
            include_lowercase=False,
            include_digits=False,
            include_symbols=False,
        )

    with pytest.raises(ValueError):
        # Length smaller than active groups count (4 groups with length 3)
        generate_secure_password(length=3, include_uppercase=True, include_lowercase=True, include_digits=True, include_symbols=True)


# ==============================================================================
# 2. Strength Analyzer Tests
# ==============================================================================

def test_analyze_empty_or_none():
    res_empty = analyze_password_strength("")
    assert res_empty["strength"] == "very_weak"
    assert res_empty["score"] == 0
    assert res_empty["length"] == 0

    res_none = analyze_password_strength(None)
    assert res_none["strength"] == "very_weak"
    assert res_none["score"] == 0


def test_analyze_common_weak_passwords():
    weak_cases = ["password", "123456", "admin123", "qwerty", "iloveyou", "P@ssw0rd123"]
    for w in weak_cases:
        res = analyze_password_strength(w)
        assert res["strength"] in ("very_weak", "weak")
        assert ("common_weak_password" in res["issues"]) or ("too_short" in res["issues"]) or ("sequential_pattern" in res["issues"]) or ("keyboard_walk_pattern" in res["issues"])


def test_analyze_sequential_patterns():
    res = analyze_password_strength("MyPass123456XyZ")
    assert "sequential_pattern" in res["issues"]
    assert res["score"] < 80


def test_analyze_keyboard_patterns():
    res = analyze_password_strength("MySecret_qwerty_99")
    assert "keyboard_walk_pattern" in res["issues"]
    assert res["score"] < 80


def test_analyze_repeated_characters():
    res = analyze_password_strength("Aaaaaa_999999_Z")
    assert "repeated_characters" in res["issues"]
    assert res["score"] < 70


def test_analyze_repeated_substrings():
    res = analyze_password_strength("testtesttest123!")
    assert "repeated_substring" in res["issues"]
    assert res["score"] < 70


def test_analyze_strong_random_passwords():
    # Long random high-entropy passwords
    strong_cases = [
        "xK9#mQ2$vL8@pZ4!",
        "7uN$kL9#mP2!qW5@zR8*",
        "G&9wT!4sQ#2vM*8xP^5k",
    ]
    for s in strong_cases:
        res = analyze_password_strength(s)
        assert res["strength"] in ("strong", "very_strong")
        assert res["score"] >= 75
        assert res["estimated_entropy"] > 60.0
        assert len(res["issues"]) == 0


def test_predictable_high_diversity_penalized():
    # Looks diverse (Upper, Lower, Number, Symbol) but is highly predictable
    res = analyze_password_strength("Qwerty123!")
    assert res["strength"] in ("very_weak", "weak")
    assert res["score"] < 50
    assert any(issue in res["issues"] for issue in ["keyboard_walk_pattern", "sequential_pattern", "common_weak_password"])


def test_privacy_and_no_exception_leakage():
    # Ensure analyzer works without error on exotic symbols and never crashes
    res = analyze_password_strength("🔒✨مرحبا1234!@#$")
    assert isinstance(res["score"], int)
    assert isinstance(res["feedback"], list)

