"""
Unit tests for Phase 5.4.2.2 — Lifecycle Hardening & Background Worker Supervision.
"""

import asyncio
import logging
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import init_db, get_connection
from services.ai.pipeline.memory import MemoryPipeline
from services.tasks.worker import TaskWorker
from main import post_shutdown


@pytest.fixture(autouse=True)
def setup_lifecycle_tests():
    init_db()
    yield


# ==========================================================================
# 1. MemoryPipeline Lifecycle Tests
# ==========================================================================

@pytest.mark.asyncio
async def test_memory_pipeline_start_and_stop():
    await MemoryPipeline.start()
    assert MemoryPipeline._running is True
    assert MemoryPipeline._worker_task is not None
    assert not MemoryPipeline._worker_task.done()

    await MemoryPipeline.stop()
    assert MemoryPipeline._running is False
    assert MemoryPipeline._worker_task is None
    assert MemoryPipeline._queue is None


@pytest.mark.asyncio
async def test_memory_pipeline_stop_before_start():
    # Calling stop when worker is not started should be safe
    MemoryPipeline._running = False
    MemoryPipeline._worker_task = None
    await MemoryPipeline.stop()
    assert MemoryPipeline._running is False


@pytest.mark.asyncio
async def test_memory_pipeline_stop_called_twice():
    await MemoryPipeline.start()
    await MemoryPipeline.stop()
    # Second call must be idempotent and raise no error
    await MemoryPipeline.stop()
    assert MemoryPipeline._running is False
    assert MemoryPipeline._worker_task is None


@pytest.mark.asyncio
async def test_memory_pipeline_stop_cancels_worker_task():
    await MemoryPipeline.start()
    task = MemoryPipeline._worker_task
    assert task is not None
    assert not task.done()

    await MemoryPipeline.stop()
    assert task.done()
    assert MemoryPipeline._worker_task is None


@pytest.mark.asyncio
async def test_memory_pipeline_stop_while_waiting_on_queue():
    await MemoryPipeline.start()
    assert MemoryPipeline._queue is not None
    assert MemoryPipeline._queue.empty()

    # Worker is waiting on empty queue; stopping should exit cleanly
    await MemoryPipeline.stop()
    assert MemoryPipeline._running is False


# ==========================================================================
# 2. TaskWorker Overlap Protection Tests
# ==========================================================================

@pytest.mark.asyncio
async def test_task_worker_normal_check():
    mock_bot = MagicMock()
    worker = TaskWorker(mock_bot)
    assert worker._is_checking is False

    with patch("services.tasks.manager.TaskManager.get_due_tasks", return_value=[]):
        res = await worker.check_tasks()
        assert res is True
        assert worker._is_checking is False


@pytest.mark.asyncio
async def test_task_worker_skips_when_already_checking():
    mock_bot = MagicMock()
    worker = TaskWorker(mock_bot)
    worker._is_checking = True

    with patch("services.tasks.manager.TaskManager.get_due_tasks") as mock_get:
        res = await worker.check_tasks()
        assert res is False
        mock_get.assert_not_called()

    # Reset guard
    worker._is_checking = False


@pytest.mark.asyncio
async def test_task_worker_releases_guard_after_exception():
    mock_bot = MagicMock()
    worker = TaskWorker(mock_bot)

    with patch("services.tasks.manager.TaskManager.get_due_tasks", side_effect=RuntimeError("DB exploded")):
        with pytest.raises(RuntimeError):
            await worker.check_tasks()

    # Guard MUST be released in finally block
    assert worker._is_checking is False


@pytest.mark.asyncio
async def test_task_worker_releases_guard_after_cancellation():
    import time
    mock_bot = MagicMock()
    worker = TaskWorker(mock_bot)

    def slow_get_due_tasks():
        time.sleep(0.2)
        return []

    with patch("services.tasks.manager.TaskManager.get_due_tasks", side_effect=slow_get_due_tasks):
        check_task = asyncio.create_task(worker.check_tasks())
        await asyncio.sleep(0.02)
        assert worker._is_checking is True

        check_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await check_task

    # Guard MUST be released even upon cancellation
    assert worker._is_checking is False


# ==========================================================================
# 3. PostgreSQL / SQLite Split-Brain Prevention Tests
# ==========================================================================

def test_db_sqlite_used_when_database_url_absent():
    with patch("database.db.DATABASE_URL", ""):
        conn = get_connection()
        try:
            from database.db import _is_sqlite_connection
            assert _is_sqlite_connection(conn) is True
        finally:
            conn.close()


def test_db_postgres_connection_failure_raises_connection_error_and_never_uses_sqlite():
    fake_pg_url = "postgresql://user:secretpassword@postgres.production.internal:5432/pfast_ai"

    with patch("database.db.DATABASE_URL", fake_pg_url), \
         patch("database.db._connect_postgresql", side_effect=RuntimeError("Cannot reach Postgres host")), \
         patch("sqlite3.connect") as mock_sqlite_connect:

        # Must raise ConnectionError
        with pytest.raises(ConnectionError) as exc_info:
            get_connection()

        assert "PostgreSQL connection failed" in str(exc_info.value)
        # CRITICAL: Must NEVER fall back to SQLite
        mock_sqlite_connect.assert_not_called()


def test_db_postgres_connection_failure_does_not_leak_secrets(caplog):
    secret_pw = "SuperSecretDbPassword123"
    fake_pg_url = f"postgresql://pfast_user:{secret_pw}@db.prod:5432/pfast_db"

    with caplog.at_level(logging.ERROR, logger="core.logger"):
        with patch("database.db.DATABASE_URL", fake_pg_url), \
             patch("database.db._connect_postgresql", side_effect=ValueError(f"Auth error with {fake_pg_url}")):

            with pytest.raises(ConnectionError) as exc_info:
                get_connection()

            # Verify no secret password in exception string
            assert secret_pw not in str(exc_info.value)

            # Verify no secret password in log records
            for record in caplog.records:
                assert secret_pw not in record.message


def test_db_postgres_valid_returns_pgconnection():
    with patch("database.db.DATABASE_URL", "postgresql://user:pass@localhost:5432/db"), \
         patch("psycopg2.connect") as mock_psycopg_connect:
        mock_psycopg_connect.return_value = MagicMock()
        conn = get_connection()
        try:
            from database.db import PGConnection
            assert isinstance(conn, PGConnection)
        finally:
            conn.close()


# ==========================================================================
# 4. Application Shutdown Lifecycle Tests
# ==========================================================================

@pytest.mark.asyncio
async def test_post_shutdown_cleans_up_all_subsystems():
    mock_app = MagicMock()
    mock_ai_engine = MagicMock()
    mock_ai_engine.shutdown = AsyncMock()

    mock_worker = MagicMock()
    mock_worker.running = True

    async def fake_worker_task_coro():
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass

    worker_asyncio_task = asyncio.create_task(fake_worker_task_coro())

    mock_app.bot_data = {
        "ai_engine": mock_ai_engine,
        "task_worker": mock_worker,
        "task_worker_task": worker_asyncio_task,
    }

    # Start MemoryPipeline before shutdown
    await MemoryPipeline.start()
    assert MemoryPipeline._running is True

    # Execute post_shutdown
    await post_shutdown(mock_app)

    # 1. Verify ai_engine.shutdown was called
    mock_ai_engine.shutdown.assert_called_once()

    # 2. Verify task_worker was marked stopped and task cancelled
    assert mock_worker.running is False
    assert worker_asyncio_task.cancelled() or worker_asyncio_task.done()

    # 3. Verify MemoryPipeline was explicitly stopped
    assert MemoryPipeline._running is False
    assert MemoryPipeline._worker_task is None
