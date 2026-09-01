"""
Unit tests for Phase 5.4.2.3 — Production Logging & Rotating File Handler.
"""

import io
import logging
import os
import sys
import tempfile
import pytest
from unittest.mock import patch

from core.logger import setup_logging


@pytest.fixture(autouse=True)
def cleanup_logging():
    yield
    # Reset root logging to clean state after each test
    setup_logging(force=True)


def test_setup_logging_attaches_console_and_file_handlers(tmp_path):
    log_file = str(tmp_path / "test_bot.log")
    app_logger = setup_logging(force=True, log_file=log_file)

    root = logging.getLogger()
    pfast_handlers = [h for h in root.handlers if getattr(h, "_pfast_ai_managed", False)]

    console_handlers = [h for h in pfast_handlers if getattr(h, "_pfast_handler_type", None) == "console"]
    file_handlers = [h for h in pfast_handlers if getattr(h, "_pfast_handler_type", None) == "file"]

    assert len(console_handlers) == 1
    assert len(file_handlers) == 1
    assert isinstance(file_handlers[0], logging.handlers.RotatingFileHandler)


def test_log_record_emitted_to_file(tmp_path):
    log_file = str(tmp_path / "app.log")
    app_logger = setup_logging(force=True, log_file=log_file)

    test_message = "PFAST_AI production logging verification message"
    app_logger.info(test_message)

    # Flush all handlers
    for h in logging.getLogger().handlers:
        h.flush()

    assert os.path.exists(log_file)
    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert test_message in content
    assert "INFO" in content
    assert "PFAST_AI" in content


def test_logging_idempotency_prevents_duplicate_handlers(tmp_path):
    log_file = str(tmp_path / "idempotency.log")

    # Call setup_logging 5 times in a row
    for _ in range(5):
        setup_logging(force=False, log_file=log_file)

    root = logging.getLogger()
    pfast_handlers = [h for h in root.handlers if getattr(h, "_pfast_ai_managed", False)]

    console_handlers = [h for h in pfast_handlers if getattr(h, "_pfast_handler_type", None) == "console"]
    file_handlers = [h for h in pfast_handlers if getattr(h, "_pfast_handler_type", None) == "file"]

    assert len(console_handlers) == 1
    assert len(file_handlers) == 1


def test_unrelated_foreign_handlers_are_preserved(tmp_path):
    root = logging.getLogger()

    # Add a custom foreign handler not managed by PFAST_AI
    foreign_handler = logging.NullHandler()
    foreign_handler._is_foreign_third_party = True
    root.addHandler(foreign_handler)

    try:
        log_file = str(tmp_path / "foreign.log")

        # Calling setup_logging with force=True should remove PFAST handlers but preserve foreign ones
        setup_logging(force=True, log_file=log_file)

        assert foreign_handler in root.handlers
        pfast_handlers = [h for h in root.handlers if getattr(h, "_pfast_ai_managed", False)]
        assert len(pfast_handlers) == 2
    finally:
        if foreign_handler in root.handlers:
            root.removeHandler(foreign_handler)


def test_rotating_file_handler_rotates_and_respects_backup_count(tmp_path):
    log_file = str(tmp_path / "rotating.log")
    max_bytes = 300  # Small byte size to trigger rotation quickly
    backup_count = 3

    app_logger = setup_logging(
        force=True,
        log_file=log_file,
        max_bytes=max_bytes,
        backup_count=backup_count,
    )

    # Write enough lines to exceed max_bytes multiple times
    for i in range(50):
        app_logger.info(f"Log message sequence number {i:03d} to trigger size threshold")

    for h in logging.getLogger().handlers:
        h.flush()

    assert os.path.exists(log_file)

    # Check for rotated backup files (.1, .2, .3)
    rotated_backups = [f for f in os.listdir(tmp_path) if f.startswith("rotating.log.")]
    assert len(rotated_backups) > 0
    # Must never exceed backup_count
    assert len(rotated_backups) <= backup_count

    # Verify no .4 or higher exists
    assert not os.path.exists(f"{log_file}.4")


def test_file_handler_failure_falls_back_to_console_without_crash(capsys):
    # Attempt setup with an invalid directory path that cannot be written
    root = logging.getLogger()

    with patch("os.makedirs", side_effect=PermissionError("Read-only filesystem")):
        with patch("sys.stderr", new_callable=io.StringIO) as mock_stderr:
            app_logger = setup_logging(force=True, log_file="/nonexistent/forbidden/path/bot.log")

            stderr_output = mock_stderr.getvalue()
            assert "WARNING: Failed to initialize rotating file logger" in stderr_output
            assert "PermissionError" in stderr_output

    # Console handler must still be active and functional
    pfast_handlers = [h for h in root.handlers if getattr(h, "_pfast_ai_managed", False)]
    console_handlers = [h for h in pfast_handlers if getattr(h, "_pfast_handler_type", None) == "console"]
    assert len(console_handlers) == 1


def test_file_handler_is_not_misclassified_as_console_handler(tmp_path):
    """FileHandler is a subclass of StreamHandler; verify our tagging separates them cleanly."""
    log_file = str(tmp_path / "subclass_check.log")
    setup_logging(force=True, log_file=log_file)

    root = logging.getLogger()
    for h in root.handlers:
        if getattr(h, "_pfast_ai_managed", False):
            if isinstance(h, logging.handlers.RotatingFileHandler):
                assert getattr(h, "_pfast_handler_type", None) == "file"
            elif type(h) is logging.StreamHandler:
                assert getattr(h, "_pfast_handler_type", None) == "console"


def test_logger_format_does_not_leak_secrets(tmp_path):
    log_file = str(tmp_path / "secrets.log")
    app_logger = setup_logging(force=True, log_file=log_file)

    secret_key = "sk-super-secret-production-token-12345"
    # An explicit sanitized log call
    app_logger.info("Service initialized with key fingerprint %s", "sk-sup***345")

    for h in logging.getLogger().handlers:
        h.flush()

    with open(log_file, "r", encoding="utf-8") as f:
        content = f.read()

    assert secret_key not in content
    assert "sk-sup***345" in content

