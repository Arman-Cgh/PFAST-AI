from typing import Dict
from openai import AsyncOpenAI

from .base import AIProvider
from .tabitoken_keys import (
    TabitokenKeyManager
)

from services.ai.config import (
    TABITOKEN_KEYS,
    TABITOKEN_BASE_URL,
    TABITOKEN_MODEL,
    MAX_TOKENS,
    TEMPERATURE,
)
from core.logger import logger


class TabitokenProvider(AIProvider):

    def __init__(self):
        self.key_manager = TabitokenKeyManager(
            TABITOKEN_KEYS
        )
        self._clients: Dict[str, AsyncOpenAI] = {}

    def _get_client(self, api_key: str) -> AsyncOpenAI:
        client = self._clients.get(api_key)
        if client is None:
            client = AsyncOpenAI(
                api_key=api_key,
                base_url=TABITOKEN_BASE_URL,
            )
            self._clients[api_key] = client
        return client

    async def generate(
        self,
        messages: list,
        model: str = None,
    ):
        attempts = len(
            TABITOKEN_KEYS
        )

        last_error = None

        for _ in range(attempts):
            api_key = (
                self.key_manager
                .get_next_key()
            )

            try:
                client = self._get_client(api_key)

                response = await client.chat.completions.create(
                    model=model or TABITOKEN_MODEL,
                    messages=messages,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                )

                self.key_manager.mark_success(
                    api_key
                )

                return (
                    response
                    .choices[0]
                    .message
                    .content
                    .strip()
                )

            except Exception as e:
                last_error = e
                logger.warning(
                    "Tabitoken key failure: %s",
                    type(e).__name__,
                )

                self.key_manager.mark_failure(
                    api_key
                )

        if last_error:
            raise last_error

        raise RuntimeError("No working Tabitoken API key available.")