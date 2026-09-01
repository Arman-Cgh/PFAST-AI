import asyncio
import inspect
import logging
import time

from services.ai.config import AI_PROVIDER, AI_PROVIDER_TIMEOUT
from services.ai.model_router import ModelRouter


logger = logging.getLogger(__name__)


class ProviderManager:

    # Maximum time allowed for one provider request.
    # Keeping this bounded prevents a stalled upstream API
    # from hanging the Telegram update indefinitely.
    PROVIDER_TIMEOUT = float(AI_PROVIDER_TIMEOUT)

    def __init__(self):
        self.providers = {}

    def get_provider(
        self,
        name=None,
    ):
        provider_name = (
            name or AI_PROVIDER
        ).strip().lower()

        if provider_name in self.providers:
            return self.providers[
                provider_name
            ]

        provider = self._load_provider(
            provider_name
        )

        self.providers[
            provider_name
        ] = provider

        return provider

    def _load_provider(
        self,
        provider_name,
    ):
        if provider_name == "groq":
            from .groq_provider import GroqProvider

            return GroqProvider()

        if provider_name == "openrouter":
            from .openrouter_provider import OpenRouterProvider

            return OpenRouterProvider()

        if provider_name == "tabitoken":
            from .tabitoken_provider import TabitokenProvider

            return TabitokenProvider()

        raise ValueError(
            f"Unsupported provider: {provider_name}"
        )

    def _get_primary_provider_name(self):
        configured = (
            AI_PROVIDER or "groq"
        ).strip().lower()

        return configured

    def get_primary_provider_name(self):
        """
        Public API for resolving the configured primary provider.
        """

        return self._get_primary_provider_name()

    def get_model(
        self,
        intent="chat",
        provider_name=None,
    ):
        provider_name = (
            provider_name
            or self.get_primary_provider_name()
        )

        return ModelRouter.select(
            provider_name,
            intent or "chat",
        )

    async def _call_provider(
        self,
        provider,
        messages,
        model=None,
    ):
        """
        Support providers with either:

            generate(messages)
        or:
            generate(messages, model=...)

        A timeout is deliberately applied here so every provider
        receives the same runtime protection.
        """

        async def invoke():
            try:
                signature = inspect.signature(
                    provider.generate
                )

                parameters = (
                    signature.parameters
                )

                accepts_model = (
                    "model" in parameters
                    or any(
                        parameter.kind
                        == inspect.Parameter.VAR_KEYWORD
                        for parameter
                        in parameters.values()
                    )
                )

            except (
                TypeError,
                ValueError,
            ):
                accepts_model = True

            if accepts_model:
                return await provider.generate(
                    messages,
                    model=model,
                )

            return await provider.generate(
                messages
            )

        timeout = getattr(
            self,
            "PROVIDER_TIMEOUT",
            ProviderManager.PROVIDER_TIMEOUT,
        )

        return await asyncio.wait_for(
            invoke(),
            timeout=timeout,
        )

    async def initialize(self):
        """
        Initialize already configured providers when they expose
        an initialization hook.

        Providers are still lazy-loaded; this method therefore
        does not force creation of unused providers.
        """

        for name, provider in tuple(
            self.providers.items()
        ):
            initialize = getattr(
                provider,
                "initialize",
                None,
            )

            if initialize is None:
                continue

            try:
                result = initialize()

                if inspect.isawaitable(
                    result
                ):
                    await result

            except Exception:
                logger.exception(
                    "Provider initialization failed: %s",
                    name,
                )
                raise

    async def shutdown(self):
        """
        Close provider resources when supported.
        """

        for name, provider in tuple(
            self.providers.items()
        ):
            close = getattr(
                provider,
                "close",
                None,
            )

            if close is None:
                continue

            try:
                result = close()

                if inspect.isawaitable(
                    result
                ):
                    await result

            except Exception:
                logger.exception(
                    "Provider shutdown failed: %s",
                    name,
                )

    @staticmethod
    def _response_text(
        response,
    ):
        """
        Normalize provider output enough for the manager to
        reject an empty upstream response safely.

        Existing provider contracts returning a string remain
        unchanged.
        """

        if isinstance(
            response,
            str,
        ):
            return response.strip()

        if isinstance(
            response,
            dict,
        ):
            text = response.get(
                "text",
                "",
            )

            if isinstance(
                text,
                str,
            ):
                return text.strip()

            return ""

        return str(
            response or ""
        ).strip()

    async def _generate_with_provider(
        self,
        provider_name,
        messages,
        intent=None,
        model=None,
    ):
        provider = self.get_provider(
            provider_name
        )

        requested_model = (
            model
            or self.get_model(
                intent=intent or "chat",
                provider_name=provider_name,
            )
        )

        start_time = time.perf_counter()

        response = await self._call_provider(
            provider,
            messages,
            requested_model,
        )

        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        text = self._response_text(
            response
        )

        if not text:
            raise RuntimeError(
                f"Provider '{provider_name}' "
                "returned an empty response."
            )

        return {
            "text": text,
            "provider": provider_name,
            "model": requested_model,
            "latency_ms": latency_ms,
        }

    async def generate(
        self,
        messages,
        intent=None,
        model=None,
        provider_name=None,
    ):
        """
        Generate an AI response using the configured primary
        provider and one controlled fallback.

        Failure categories handled by the same mechanism:
            - timeout
            - connection errors
            - provider exceptions
            - empty responses
        """

        primary_name = (
            provider_name
            or self.get_primary_provider_name()
        )

        primary_name = (
            primary_name
            .strip()
            .lower()
        )

        try:
            return await self._generate_with_provider(
                provider_name=primary_name,
                messages=messages,
                intent=intent,
                model=model,
            )

        except asyncio.TimeoutError:
            primary_error = TimeoutError(
                f"Provider '{primary_name}' "
                f"timed out after "
                f"{self.PROVIDER_TIMEOUT:g} seconds."
            )

            logger.warning(
                "%s",
                primary_error,
            )

        except Exception as exc:
            primary_error = exc

            logger.warning(
                "Primary provider '%s' failed: %s",
                primary_name,
                exc,
            )

        fallback_name = (
            self.get_fallback_provider_name(
                primary_name
            )
        )

        if (
            not fallback_name
            or fallback_name == primary_name
        ):
            raise primary_error

        logger.info(
            "Trying fallback provider '%s' "
            "after '%s' failure",
            fallback_name,
            primary_name,
        )

        try:
            fallback_result = (
                await self._generate_with_provider(
                    provider_name=fallback_name,
                    messages=messages,
                    intent=intent,
                    model=None,
                )
            )

            fallback_result[
                "fallback"
            ] = True

            fallback_result[
                "primary_error"
            ] = str(
                primary_error
            )

            return fallback_result

        except asyncio.TimeoutError:
            logger.exception(
                "Fallback provider '%s' timed out",
                fallback_name,
            )
            raise

        except Exception:
            logger.exception(
                "Fallback provider '%s' failed",
                fallback_name,
            )
            raise

    def get_fallback_provider_name(
        self,
        failed_provider,
    ):
        fallback_map = {
            "groq": "openrouter",
            "openrouter": "groq",
            "tabitoken": "groq",
        }

        return fallback_map.get(
            (
                failed_provider
                or ""
            ).strip().lower()
        )

    def get_fallback_provider(
        self,
        failed_provider,
    ):
        fallback_name = (
            self.get_fallback_provider_name(
                failed_provider
            )
        )

        if not fallback_name:
            raise ValueError(
                f"No fallback provider for: "
                f"{failed_provider}"
            )

        return self.get_provider(
            fallback_name
        )

    def get_provider_name(
        self,
        provider,
    ):
        mapping = {
            "GroqProvider": "groq",
            "OpenRouterProvider": "openrouter",
            "TabitokenProvider": "tabitoken",
        }

        return mapping.get(
            provider.__class__.__name__,
            "unknown",
        )