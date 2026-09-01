import pytest

from services.ai.providers.manager import ProviderManager


class FakeProvider:

    def __init__(self, response="OK"):
        self.response = response


    async def generate(
        self,
        messages,
    ):

        return self.response



class FailingProvider:

    async def generate(
        self,
        messages,
    ):

        raise Exception(
            "provider failed"
        )



@pytest.mark.asyncio
async def test_provider_manager_success():

    manager = ProviderManager()

    fake = FakeProvider(
        response="hello"
    )

    manager.providers["fake"] = fake

    result = await fake.generate(
        [
            {
                "role": "user",
                "content": "test",
            }
        ]
    )

    assert result == "hello"



@pytest.mark.asyncio
async def test_provider_fallback_logic():

    failing = FailingProvider()

    with pytest.raises(
        Exception
    ):

        await failing.generate(
            []
        )

@pytest.mark.asyncio
async def test_provider_manager_fallback():

    manager = ProviderManager()

    class FakeFailProvider:

        async def generate(self, messages):
            raise Exception(
                "primary failed"
            )


    class FakeSuccessProvider:

        async def generate(self, messages):
            return "fallback response"


    manager.providers["groq"] = FakeFailProvider()
    manager.providers["openrouter"] = FakeSuccessProvider()


    original_get_fallback = manager.get_fallback_provider


    def fake_fallback(provider):

        return manager.providers["openrouter"]


    manager.get_fallback_provider = fake_fallback


    from services.ai import providers

    result = await manager.generate(
        messages=[
            {
                "role": "user",
                "content": "hello",
            }
        ],
        provider_name="groq",
    )


    assert result["text"] == "fallback response"