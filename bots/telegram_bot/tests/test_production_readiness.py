import asyncio
import pytest
from unittest.mock import AsyncMock, patch

from services.ai.providers.manager import ProviderManager
from services.ai.providers.tabitoken_provider import TabitokenProvider
from services.ai.config import AI_MAX_TOKENS, AI_TEMPERATURE, AI_PROVIDER_TIMEOUT


class FailingPrimaryProvider:
    async def generate(self, messages, model=None):
        raise RuntimeError("Primary API connection failed")


class SuccessfulFallbackProvider:
    async def generate(self, messages, model=None):
        return "پاسخ از ارائه‌دهنده پشتیبان"


@pytest.mark.asyncio
async def test_provider_fallback_on_primary_failure():
    manager = ProviderManager()
    manager.providers["groq"] = FailingPrimaryProvider()
    manager.providers["openrouter"] = SuccessfulFallbackProvider()

    result = await manager.generate(
        messages=[{"role": "user", "content": "سلام"}],
        provider_name="groq",
    )

    assert result["fallback"] is True
    assert result["provider"] == "openrouter"
    assert result["text"] == "پاسخ از ارائه‌دهنده پشتیبان"
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_provider_timeout_handling():
    class SlowProvider:
        async def generate(self, messages, model=None):
            await asyncio.sleep(0.5)
            return "پاسخ کند"

    manager = ProviderManager()
    manager.PROVIDER_TIMEOUT = 0.05
    manager.providers["groq"] = SlowProvider()
    manager.providers["openrouter"] = SuccessfulFallbackProvider()

    result = await manager.generate(
        messages=[{"role": "user", "content": "سلام"}],
        provider_name="groq",
    )

    assert result["fallback"] is True
    assert result["provider"] == "openrouter"
    assert result["text"] == "پاسخ از ارائه‌دهنده پشتیبان"


def test_config_defaults_and_types():
    assert isinstance(AI_MAX_TOKENS, int)
    assert AI_MAX_TOKENS > 0
    assert isinstance(AI_TEMPERATURE, float)
    assert 0.0 <= AI_TEMPERATURE <= 2.0
    assert isinstance(AI_PROVIDER_TIMEOUT, float)
    assert AI_PROVIDER_TIMEOUT > 0


@pytest.mark.asyncio
async def test_tabitoken_client_reuse(monkeypatch):
    monkeypatch.setattr("services.ai.providers.tabitoken_provider.TABITOKEN_KEYS", ["test_key_1", "test_key_2"])

    provider = TabitokenProvider()
    client1 = provider._get_client("test_key_1")
    client2 = provider._get_client("test_key_1")
    client3 = provider._get_client("test_key_2")

    # Verify identical client instance is reused for same key
    assert client1 is client2
    # Different key gets distinct client
    assert client1 is not client3
