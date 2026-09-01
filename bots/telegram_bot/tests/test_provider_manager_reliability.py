import asyncio

import pytest

from services.ai.providers.manager import ProviderManager


class SuccessfulProvider:
    async def generate(
        self,
        messages,
        model=None,
    ):
        return "primary response"


class FallbackProvider:
    async def generate(
        self,
        messages,
        model=None,
    ):
        return "fallback response"


class FailingProvider:
    async def generate(
        self,
        messages,
        model=None,
    ):
        raise RuntimeError(
            "primary provider failed"
        )


class EmptyProvider:
    async def generate(
        self,
        messages,
        model=None,
    ):
        return ""


class TimeoutProvider:
    async def generate(
        self,
        messages,
        model=None,
    ):
        await asyncio.sleep(
            0.05
        )
        return "too late"


@pytest.mark.asyncio
async def test_primary_provider_success():
    manager = ProviderManager()

    manager.providers["groq"] = (
        SuccessfulProvider()
    )

    result = await manager.generate(
        messages=[
            {
                "role": "user",
                "content": "سلام",
            }
        ],
        provider_name="groq",
        model="test-model",
    )

    assert result["text"] == "primary response"
    assert result["provider"] == "groq"
    assert result["model"] == "test-model"
    assert result.get("fallback") is not True


@pytest.mark.asyncio
async def test_primary_failure_uses_fallback():
    manager = ProviderManager()

    manager.providers["groq"] = (
        FailingProvider()
    )

    manager.providers["openrouter"] = (
        FallbackProvider()
    )

    result = await manager.generate(
        messages=[
            {
                "role": "user",
                "content": "سلام",
            }
        ],
        provider_name="groq",
        model="test-model",
    )

    assert result["text"] == "fallback response"
    assert result["provider"] == "openrouter"
    assert result["fallback"] is True
    assert (
        "primary provider failed"
        in result["primary_error"]
    )


@pytest.mark.asyncio
async def test_empty_primary_response_uses_fallback():
    manager = ProviderManager()

    manager.providers["groq"] = (
        EmptyProvider()
    )

    manager.providers["openrouter"] = (
        FallbackProvider()
    )

    result = await manager.generate(
        messages=[
            {
                "role": "user",
                "content": "سلام",
            }
        ],
        provider_name="groq",
        model="test-model",
    )

    assert result["text"] == "fallback response"
    assert result["provider"] == "openrouter"
    assert result["fallback"] is True


@pytest.mark.asyncio
async def test_primary_timeout_uses_fallback(
    monkeypatch,
):
    manager = ProviderManager()

    manager.providers["groq"] = (
        TimeoutProvider()
    )

    manager.providers["openrouter"] = (
        FallbackProvider()
    )

    monkeypatch.setattr(
        ProviderManager,
        "PROVIDER_TIMEOUT",
        0.01,
    )

    result = await manager.generate(
        messages=[
            {
                "role": "user",
                "content": "سلام",
            }
        ],
        provider_name="groq",
        model="test-model",
    )

    assert result["text"] == "fallback response"
    assert result["provider"] == "openrouter"
    assert result["fallback"] is True
    assert (
        "timed out"
        in result["primary_error"]
    )


@pytest.mark.asyncio
async def test_no_fallback_reraises_primary_error():
    manager = ProviderManager()

    manager.providers["custom"] = (
        FailingProvider()
    )

    with pytest.raises(
        RuntimeError,
        match="primary provider failed",
    ):
        await manager.generate(
            messages=[
                {
                    "role": "user",
                    "content": "سلام",
                }
            ],
            provider_name="custom",
            model="test-model",
        )


@pytest.mark.asyncio
async def test_fallback_failure_is_propagated():
    manager = ProviderManager()

    manager.providers["groq"] = (
        FailingProvider()
    )

    class BrokenFallback:
        async def generate(
            self,
            messages,
            model=None,
        ):
            raise RuntimeError(
                "fallback provider failed"
            )

    manager.providers["openrouter"] = (
        BrokenFallback()
    )

    with pytest.raises(
        RuntimeError,
        match="fallback provider failed",
    ):
        await manager.generate(
            messages=[
                {
                    "role": "user",
                    "content": "سلام",
                }
            ],
            provider_name="groq",
            model="test-model",
        )


@pytest.mark.asyncio
async def test_shutdown_closes_loaded_providers():
    manager = ProviderManager()

    class ClosableProvider:
        def __init__(self):
            self.closed = False

        async def close(self):
            self.closed = True

    provider = ClosableProvider()

    manager.providers["groq"] = provider

    await manager.shutdown()

    assert provider.closed is True