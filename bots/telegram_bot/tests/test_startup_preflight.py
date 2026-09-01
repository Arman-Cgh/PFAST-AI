"""
Unit tests for Startup Pre-flight Validation & Fail-Fast Gate.
"""

import os
import pytest
from unittest.mock import MagicMock, patch

from database.db import init_db
from services.system.preflight import (
    StartupPreflight,
    PreflightError,
    PreflightReport,
)


@pytest.fixture(autouse=True)
def setup_preflight_tests():
    init_db()
    yield


# ==========================================================================
# 1. Telegram Token Validation Tests
# ==========================================================================

def test_telegram_token_valid():
    valid_token = "123456789:ABCDefgh-1234567890abcdefgh_12345"
    res = StartupPreflight.validate_telegram_token(valid_token)
    assert res.passed is True
    assert res.critical is True
    assert "ABCDefgh" not in res.details  # Raw token secret is not leaked


def test_telegram_token_missing_or_empty():
    res_empty = StartupPreflight.validate_telegram_token("")
    assert res_empty.passed is False
    assert "missing or empty" in res_empty.details

    res_none = StartupPreflight.validate_telegram_token(None)
    # If TELEGRAM_TOKEN in config is empty, should fail
    with patch("services.system.preflight.TELEGRAM_TOKEN", ""):
        res = StartupPreflight.validate_telegram_token(None)
        assert res.passed is False


def test_telegram_token_malformed():
    invalid_tokens = [
        "not_a_valid_token",
        "12345:short",
        "invalid_bot_id:abcdefghijklmnopqrstuvwxyz",
        "123456:invalid characters in token!@#$",
    ]
    for token in invalid_tokens:
        res = StartupPreflight.validate_telegram_token(token)
        assert res.passed is False
        assert "format is invalid" in res.details


def test_telegram_token_never_logs_raw_secret():
    secret_token = "987654321:SECRET_TOKEN_VALUE_XYZ1234567890"
    res = StartupPreflight.validate_telegram_token(secret_token)
    assert res.passed is True
    assert "SECRET_TOKEN_VALUE" not in res.details
    assert "SECRET_TOKEN_VALUE" not in str(res.metadata)


# ==========================================================================
# 2. AI Provider Configuration Validation Tests
# ==========================================================================

def test_ai_provider_groq_valid():
    with patch("services.ai.config.AI_PROVIDER", "groq"), \
         patch("services.ai.config.GROQ_API_KEY", "gsk_fake_valid_groq_api_key_12345678"):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is True
        assert "groq" in res.details
        assert "fake_valid" not in res.details  # Key masked


def test_ai_provider_groq_missing_key():
    with patch("services.ai.config.AI_PROVIDER", "groq"), \
         patch("services.ai.config.GROQ_API_KEY", ""):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is False
        assert "GROQ_API_KEY is missing" in res.details


def test_ai_provider_tabitoken_valid():
    with patch("services.ai.config.AI_PROVIDER", "tabitoken"), \
         patch("services.ai.config.TABITOKEN_KEYS", ["sk-tabi-key-1", "sk-tabi-key-2"]):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is True
        assert "tabitoken" in res.details
        assert "2 active key(s)" in res.details


def test_ai_provider_tabitoken_empty_keys():
    with patch("services.ai.config.AI_PROVIDER", "tabitoken"), \
         patch("services.ai.config.TABITOKEN_KEYS", []):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is False
        assert "TABITOKEN_KEYS contains no valid API keys" in res.details


def test_ai_provider_openrouter_valid():
    with patch("services.ai.config.AI_PROVIDER", "openrouter"), \
         patch("services.ai.config.OPENROUTER_API_KEY", "sk-or-fake-openrouter-key-12345"):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is True
        assert "openrouter" in res.details


def test_ai_provider_openrouter_missing_key():
    with patch("services.ai.config.AI_PROVIDER", "openrouter"), \
         patch("services.ai.config.OPENROUTER_API_KEY", ""):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is False
        assert "OPENROUTER_API_KEY is missing" in res.details


def test_ai_provider_unsupported_name():
    with patch("services.ai.config.AI_PROVIDER", "unsupported_provider_xyz"):
        res = StartupPreflight.validate_ai_provider()
        assert res.passed is False
        assert "Unsupported AI_PROVIDER" in res.details


# ==========================================================================
# 3. Database Connectivity & Transactional Rollback Tests
# ==========================================================================

def test_database_validation_success():
    res = StartupPreflight.validate_database()
    assert res.passed is True
    assert "read and transactional write/rollback verified" in res.details


def test_database_validation_connection_failure():
    with patch("services.system.preflight.get_connection", side_effect=RuntimeError("DB offline")):
        res = StartupPreflight.validate_database()
        assert res.passed is False
        assert "Database connection error" in res.details


# ==========================================================================
# 4. Filesystem Validation Tests
# ==========================================================================

def test_filesystem_validation_success():
    res = StartupPreflight.validate_filesystem()
    assert res.passed is True
    assert "Required directories verified" in res.details


def test_filesystem_validation_unwritable_path():
    with patch("os.makedirs", side_effect=PermissionError("Permission denied")):
        res = StartupPreflight.validate_filesystem()
        assert res.passed is False
        assert "not writable" in res.details


# ==========================================================================
# 5. Full Pre-flight & Fail-Fast Gate Tests
# ==========================================================================

def test_run_all_success():
    valid_token = "123456789:ABCDefgh-1234567890abcdefgh_12345"
    with patch("services.system.preflight.TELEGRAM_TOKEN", valid_token), \
         patch("services.ai.config.AI_PROVIDER", "groq"), \
         patch("services.ai.config.GROQ_API_KEY", "gsk_valid_key_1234567890"):
        report = StartupPreflight.run_all(fail_fast=True)
        assert isinstance(report, PreflightReport)
        assert report.passed is True
        assert len(report.results) == 4
        assert "✅ Startup Pre-flight Report" in report.summary()


def test_run_all_fail_fast_raises_exception():
    with patch("services.system.preflight.TELEGRAM_TOKEN", ""):
        with pytest.raises(PreflightError) as exc_info:
            StartupPreflight.run_all(fail_fast=True)
        assert "Startup pre-flight validation failed" in str(exc_info.value)


def test_run_all_without_fail_fast_returns_report():
    with patch("services.system.preflight.TELEGRAM_TOKEN", ""):
        report = StartupPreflight.run_all(fail_fast=False)
        assert report.passed is False
        assert any(not r.passed for r in report.results)


# ==========================================================================
# 6. Main Startup Polling Protection Invariant
# ==========================================================================

def test_main_aborts_and_never_polls_on_preflight_failure():
    """Verify that when preflight fails, application.run_polling() is NEVER executed."""
    with patch("services.system.preflight.StartupPreflight.run_all", side_effect=PreflightError("Token invalid")):
        with patch("main.build_application") as mock_build:
            from main import main
            with pytest.raises(PreflightError):
                main()
            mock_build.assert_not_called()

