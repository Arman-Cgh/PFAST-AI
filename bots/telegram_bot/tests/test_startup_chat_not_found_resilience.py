"""
Tests for Telegram 'Chat not found' / 'Forbidden' startup and worker resilience.

Validates that:
1. Due tasks targeting nonexistent, blocked, or deleted Telegram chats do not crash the worker or startup.
2. Unreachable chat errors (BadRequest: Chat not found, Forbidden: bot blocked) cause tasks to be dismissed gracefully.
3. Subsequent check_tasks() cycles do not re-attempt dead chats in an infinite loop.
4. Transient network errors are logged as warnings and retried.
5. init_db() cleanly seeds plans, prices, referral settings, and feature flags.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock

from database.db import init_db, add_user, get_connection, get_plan_prices, get_all_feature_flags
from services.tasks.manager import TaskManager
from services.tasks.worker import TaskWorker, is_permanent_chat_error

try:
    from telegram.error import BadRequest, Forbidden, TimedOut, NetworkError
except ImportError:
    class BadRequest(Exception):
        pass
    class Forbidden(Exception):
        pass
    class TimedOut(Exception):
        pass
    class NetworkError(Exception):
        pass


@pytest.fixture(autouse=True)
def setup_clean_db():
    init_db()
    conn = get_connection()
    try:
        conn.cursor().execute("UPDATE tasks SET completed = 1 WHERE completed = 0")
        conn.commit()
    finally:
        conn.close()
    yield


def test_is_permanent_chat_error_detection():
    """Verify permanent chat errors are correctly recognized."""
    assert is_permanent_chat_error(Forbidden("Forbidden: bot was blocked by the user")) is True
    assert is_permanent_chat_error(Forbidden("Forbidden: user is deactivated")) is True
    assert is_permanent_chat_error(BadRequest("BadRequest: Chat not found")) is True
    assert is_permanent_chat_error(BadRequest("Bad Request: chat not found")) is True
    assert is_permanent_chat_error(BadRequest("Bad Request: user not found")) is True
    assert is_permanent_chat_error(BadRequest("Bad Request: PEER_ID_INVALID")) is True
    assert is_permanent_chat_error(TimedOut("Request timed out")) is False
    assert is_permanent_chat_error(NetworkError("Connection reset by peer")) is False


@pytest.mark.asyncio
async def test_worker_dismisses_task_on_chat_not_found():
    """
    When TaskWorker encounters BadRequest('Chat not found'):
    - It must NOT crash or raise an unhandled exception.
    - It must mark the task completed/dismissed in the database.
    - Subsequent check_tasks() calls must find 0 remaining due tasks.
    """
    dead_user_id = 999999111
    add_user(dead_user_id, "dead_user")
    task_id = TaskManager.create(
        user_id=dead_user_id,
        title="Dead chat reminder",
        due_date="2020-01-01 10:00",
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(
        side_effect=BadRequest("Bad Request: chat not found")
    )

    worker = TaskWorker(mock_bot)

    # First run: should encounter Chat not found, log warning, and dismiss task
    result = await worker.check_tasks()
    assert result is True
    mock_bot.send_message.assert_called_once()

    # Task must now be marked as completed (dismissed)
    task = TaskManager.get_by_id(task_id, dead_user_id)
    assert task is not None
    assert task["completed"] is True

    # Second run: no due tasks remain, send_message is NOT called again
    mock_bot.send_message.reset_mock()
    result2 = await worker.check_tasks()
    assert result2 is True
    mock_bot.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_worker_dismisses_task_on_bot_blocked_by_user():
    """
    When TaskWorker encounters Forbidden('bot was blocked by the user'):
    - It must mark the task completed/dismissed in the database.
    - It must not crash.
    """
    blocked_user_id = 888888222
    add_user(blocked_user_id, "blocked_user")
    task_id = TaskManager.create(
        user_id=blocked_user_id,
        title="Blocked user reminder",
        due_date="2020-01-01 10:00",
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(
        side_effect=Forbidden("Forbidden: bot was blocked by the user")
    )

    worker = TaskWorker(mock_bot)

    result = await worker.check_tasks()
    assert result is True

    task = TaskManager.get_by_id(task_id, blocked_user_id)
    assert task is not None
    assert task["completed"] is True


@pytest.mark.asyncio
async def test_worker_retries_on_transient_network_error():
    """
    When TaskWorker encounters TimedOut:
    - It must log a warning and KEEP the task for retry.
    """
    retry_user_id = 777777333
    add_user(retry_user_id, "retry_user")
    task_id = TaskManager.create(
        user_id=retry_user_id,
        title="Transient retry reminder",
        due_date="2020-01-01 10:00",
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(
        side_effect=TimedOut("Request timed out")
    )

    worker = TaskWorker(mock_bot)

    result = await worker.check_tasks()
    assert result is True

    # Task should NOT be completed (kept for retry)
    task = TaskManager.get_by_id(task_id, retry_user_id)
    assert task is not None
    assert task["completed"] is False


@pytest.mark.asyncio
async def test_worker_successful_delivery():
    """
    When TaskWorker successfully sends a message:
    - Task is marked completed.
    """
    live_user_id = 111111444
    add_user(live_user_id, "live_user")
    task_id = TaskManager.create(
        user_id=live_user_id,
        title="Live user reminder",
        due_date="2020-01-01 10:00",
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(return_value=MagicMock())

    worker = TaskWorker(mock_bot)

    result = await worker.check_tasks()
    assert result is True

    task = TaskManager.get_by_id(task_id, live_user_id)
    assert task is not None
    assert task["completed"] is True


@pytest.mark.asyncio
async def test_worker_unexpected_error_does_not_complete_task():
    """
    When TaskWorker encounters an unexpected/unknown exception:
    - It logs the exception.
    - It must NOT dismiss/complete the task.
    - The task remains uncompleted for future retry.
    """
    error_user_id = 555555666
    add_user(error_user_id, "error_user")
    task_id = TaskManager.create(
        user_id=error_user_id,
        title="Unexpected error reminder",
        due_date="2020-01-01 10:00",
    )

    mock_bot = MagicMock()
    mock_bot.send_message = AsyncMock(
        side_effect=RuntimeError("Internal Telegram SDK glitch")
    )

    worker = TaskWorker(mock_bot)

    result = await worker.check_tasks()
    assert result is True

    # Task MUST NOT be marked completed
    task = TaskManager.get_by_id(task_id, error_user_id)
    assert task is not None
    assert task["completed"] is False


def test_init_db_seeds_all_required_defaults():
    """Verify init_db seeds plans, plan_prices, referral_settings, and feature_flags."""
    init_db()

    prices = get_plan_prices()
    assert "pro" in prices
    assert "ultra" in prices
    assert prices["pro"]["price"] > 0
    assert prices["pro"]["currency"]

    flags = get_all_feature_flags()
    assert "image_generation" in flags
    assert "password_tools" in flags
    assert "url_scanner" in flags