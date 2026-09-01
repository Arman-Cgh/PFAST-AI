"""
Step 5.4.1 Security Hardening Regression Tests.

Each test protects a specific bug fixed during the audit.
"""
import logging
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from database.db import init_db, set_feature_flag
from utils.feature_gate import clear_feature_cache


@pytest.fixture(autouse=True)
def setup_security_tests():
    init_db()
    clear_feature_cache()
    yield
    clear_feature_cache()


# ==========================================================================
# 1. rate_limit.py — no print() output, uses logger.debug
# ==========================================================================

def test_rate_limit_no_print_to_stdout(capsys):
    """Rate limiter must not print anything to stdout."""
    from middlewares.rate_limit import check_rate_limit
    with patch("middlewares.rate_limit.get_user_limits", return_value={"cooldown_seconds": 5}):
        check_rate_limit(999001)
    captured = capsys.readouterr()
    assert captured.out == "", f"Unexpected stdout output: {captured.out!r}"


def test_rate_limit_uses_logger_debug(caplog):
    """Rate limiter must emit structured logger messages, not print()."""
    from middlewares.rate_limit import check_rate_limit
    with caplog.at_level(logging.DEBUG, logger="middlewares.rate_limit"):
        with patch("middlewares.rate_limit.get_user_limits", return_value={"cooldown_seconds": 5}):
            check_rate_limit(999002)
    assert len(caplog.records) > 0


def test_rate_limit_bounded_cache_eviction():
    """user_last_message dict must not grow past _MAX_CACHE_SIZE."""
    from middlewares import rate_limit
    from middlewares.rate_limit import _MAX_CACHE_SIZE, user_last_message, check_rate_limit

    # Seed the cache near capacity to trigger eviction
    rate_limit.user_last_message = {
        i: time.time() - (i % 600) for i in range(_MAX_CACHE_SIZE)
    }
    with patch("middlewares.rate_limit.get_user_limits", return_value={"cooldown_seconds": 0}):
        check_rate_limit(9999999)  # This should trigger eviction

    assert len(rate_limit.user_last_message) <= _MAX_CACHE_SIZE


def test_rate_limit_allows_first_message():
    """First message from a new user must always be allowed."""
    from middlewares.rate_limit import check_rate_limit, user_last_message
    uid = 888001
    user_last_message.pop(uid, None)
    with patch("middlewares.rate_limit.get_user_limits", return_value={"cooldown_seconds": 10}):
        result = check_rate_limit(uid)
    assert result is True


def test_rate_limit_blocks_within_cooldown():
    """Subsequent message within cooldown window must be blocked."""
    import middlewares.rate_limit as rl
    uid = 888002
    rl.user_last_message[uid] = time.time()
    with patch("middlewares.rate_limit.get_user_limits", return_value={"cooldown_seconds": 60}):
        result = rl.check_rate_limit(uid)
    assert result is False


# ==========================================================================
# 2. profile.py — no print() for errors
# ==========================================================================

def test_profile_load_no_print_on_error(capsys):
    """Profile load failure must not print() to stdout."""
    from services.ai.profile import load_profile
    with patch("services.ai.profile.get_profile", side_effect=Exception("DB exploded")):
        result = load_profile(777001)
    captured = capsys.readouterr()
    assert captured.out == ""
    assert isinstance(result, dict)


def test_profile_load_logs_on_error(caplog):
    """Profile load failure must log a warning."""
    from services.ai.profile import load_profile
    with caplog.at_level(logging.WARNING, logger="services.ai.profile"):
        with patch("services.ai.profile.get_profile", side_effect=Exception("DB fail")):
            load_profile(777002)
    assert any("777002" in r.message for r in caplog.records)


# ==========================================================================
# 3. context.py — silent ContextOptimizer failure must be logged
# ==========================================================================

def test_context_optimizer_failure_is_logged(caplog):
    """ContextOptimizer failure must emit a warning, not silently pass."""
    from services.ai.context import ContextBuilder
    with caplog.at_level(logging.WARNING, logger="services.ai.context"):
        with patch("services.ai.context.ContextOptimizer.optimize", side_effect=RuntimeError("broken")):
            with patch("services.ai.context.MemoryService.get_memory", return_value={}):
                with patch("services.ai.context.MemoryService.get_state", return_value={}):
                    with patch("services.ai.context.ProfileManager.get", return_value={}):
                        with patch("services.ai.context.get_history", return_value=[]):
                            ContextBuilder(123456).build()
    assert any("ContextOptimizer" in r.message for r in caplog.records)


# ==========================================================================
# 4. tabitoken_keys.py — stats() must not expose raw API keys
# ==========================================================================

def test_tabitoken_stats_does_not_expose_raw_keys():
    """TabitokenKeyManager.stats() must return masked fingerprints, not raw keys."""
    from services.ai.providers.tabitoken_keys import TabitokenKeyManager
    mgr = TabitokenKeyManager(["sk-verylongapikey1234", "sk-anotherrealkey5678"])
    stats = mgr.stats()

    raw_keys = ["sk-verylongapikey1234", "sk-anotherrealkey5678"]
    for raw_key in raw_keys:
        assert raw_key not in stats, f"Raw key exposed in stats output: {raw_key!r}"

    for masked_key in stats:
        assert "***" in masked_key, f"Stats key not masked: {masked_key!r}"


# ==========================================================================
# 5. tabitoken_provider.py — warning log must not include raw error bodies
# ==========================================================================

@pytest.mark.asyncio
async def test_tabitoken_provider_logs_only_type_on_failure(caplog):
    """Tabitoken provider must log only exception type, not full exception body."""
    from services.ai.providers.tabitoken_provider import TabitokenProvider
    from services.ai.providers.tabitoken_keys import TabitokenKeyManager

    fake_key = "sk-fake12345678"

    provider = TabitokenProvider.__new__(TabitokenProvider)
    provider.key_manager = TabitokenKeyManager([fake_key])
    provider._clients = {}

    # Make the API call raise an exception with a "sensitive" string
    sensitive_msg = "Authorization header=Bearer sk-fake12345678 was rejected"
    with caplog.at_level(logging.WARNING):
        with patch.object(provider, "_get_client") as mock_client:
            mock_api = MagicMock()
            mock_api.chat.completions.create = AsyncMock(
                side_effect=ValueError(sensitive_msg)
            )
            mock_client.return_value = mock_api

            with pytest.raises(ValueError):
                await provider.generate([{"role": "user", "content": "hello"}])

    for record in caplog.records:
        if "Tabitoken key failure" in record.message:
            assert sensitive_msg not in record.message, \
                "Sensitive exception body leaked into log!"
            assert fake_key not in record.message, \
                "Raw API key leaked into log!"


# ==========================================================================
# 6. user_callbacks.py verify_payment — ownership enforcement
# ==========================================================================

@pytest.mark.asyncio
async def test_verify_payment_rejects_wrong_user():
    """Payment verification must reject user who doesn't own the payment."""
    from handlers.user_callbacks import user_callback

    attacker_id = 666001
    real_owner_id = 666002

    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "verify_payment:42:AUTH123"
    query.from_user = MagicMock()
    query.from_user.id = attacker_id
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    # Payment exists but belongs to real_owner_id, not the attacker
    mock_payment = {"id": 42, "user_id": real_owner_id, "status": "pending"}

    # get_payment is a lazy import inside the callback — patch at source module
    with patch("services.billing.payment_service.get_payment_request", return_value=mock_payment):
        with patch("services.billing.payment_service.gateway_verify_payment", return_value=False):
            await user_callback(update, context)

    # Should have been rejected due to ownership mismatch
    call_text = query.edit_message_text.call_args[0][0]
    assert "مجاز نیست" in call_text or "دسترسی" in call_text


@pytest.mark.asyncio
async def test_verify_payment_allows_owner():
    """Payment verification must allow the payment owner to verify."""
    from handlers.user_callbacks import user_callback

    owner_id = 666003

    update = MagicMock()
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "verify_payment:43:AUTH456"
    query.from_user = MagicMock()
    query.from_user.id = owner_id
    update.callback_query = query
    context = MagicMock()
    context.user_data = {}

    mock_payment = {"id": 43, "user_id": owner_id, "status": "pending", "plan_name": "pro", "duration_days": 30}

    # Patch at source so lazy import sees the mock
    with patch("services.billing.payment_service.get_payment_request", return_value=mock_payment):
        with patch("services.billing.payment_service.gateway_verify_payment", return_value=True):
            with patch("services.billing.payment_service.create_subscription"):
                with patch("services.billing.payment_service.update_user_plan"):
                    with patch("services.billing.payment_service.update_payment_request_status"):
                        await user_callback(update, context)

    call_text = query.edit_message_text.call_args[0][0]
    assert "تأیید شد" in call_text


# ==========================================================================
# 7. pipeline/response.py — cache write failure must be logged, not silenced
# ==========================================================================

@pytest.mark.asyncio
async def test_cache_write_failure_is_logged(caplog):
    """Cache write failures must be logged as warnings, not silently swallowed."""
    from services.ai.pipeline.response import ResponsePipeline

    mock_cache = MagicMock()
    mock_cache.is_cacheable = MagicMock(return_value=True)
    mock_cache.generate_key = MagicMock(return_value="cache_key_123")
    mock_cache.get = AsyncMock(return_value=None)
    mock_cache.set = AsyncMock(side_effect=RuntimeError("disk full"))

    pipeline = ResponsePipeline(
        provider_manager=MagicMock(
            generate=AsyncMock(
                return_value={"text": "test response", "provider": "test"}
            )
        ),
        cache=mock_cache,
    )

    with caplog.at_level(logging.WARNING):
        with patch.object(pipeline, "build_messages", AsyncMock(return_value=[])):
            result = await pipeline.generate(123, "hello", "chat", use_cache=True)

    assert result.get("response") == "test response"
    assert any("cache" in r.message.lower() for r in caplog.records), \
        "Expected a warning log for cache write failure"
