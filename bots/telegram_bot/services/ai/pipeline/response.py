from typing import Any, Dict
import json
import hashlib

from services.ai.context import ContextBuilder
from services.ai.prompt import build_prompt
from services.ai.response_guard import clean_response


class ResponsePipeline:

    def __init__(
        self,
        provider_manager,
        cache,
    ):
        self.provider_manager = provider_manager
        self.cache = cache

    async def build_messages(
        self,
        user_id: int,
        message: str,
        intent: str,
    ):
        context = ContextBuilder(
            user_id
        ).build(
            intent=intent,
            user_message=message,
        )

        return build_prompt(
            user_id=user_id,
            user_message=message,
            context=context,
            intent=intent,
        )

    def _build_prompt_fingerprint(
        self,
        messages,
        intent,
    ):
        try:
            payload = json.dumps(
                {
                    "intent": str(
                        intent or "chat"
                    ),
                    "messages": messages,
                },
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        except (
            TypeError,
            ValueError,
        ):
            payload = str(messages)

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    async def generate(
        self,
        user_id: int,
        message: str,
        intent: str,
        use_cache: bool = True,
    ) -> Dict[str, Any]:

        can_cache = (
            use_cache
            and self.cache.is_cacheable(
                intent,
                message,
            )
        )

        # Build the actual prompt before cache lookup.
        # This prevents different user context/history from
        # sharing the same cache entry.
        messages = await self.build_messages(
            user_id=user_id,
            message=message,
            intent=intent,
        )

        cache_key = self.cache.generate_key(
            user_message=message,
            intent=intent,
            prompt_payload=messages,
        )

        if can_cache:
            try:
                cached = await self.cache.get(
                    user_id,
                    cache_key,
                )

            except Exception:
                cached = None

            if cached:
                return {
                    "response": cached,
                    "cached": True,
                    "intent": {
                        "intent": "cached",
                        "confidence": 1,
                        "source": "cache",
                    },
                    "provider": "cache",
                }

        result = await self.provider_manager.generate(
            messages
        )

        if not isinstance(
            result,
            dict,
        ):
            result = {}

        response = clean_response(
            result.get(
                "text",
                "",
            )
        )

        provider = result.get(
            "provider",
            "unknown",
        )

        if response and can_cache:
            try:
                await self.cache.set(
                    user_id,
                    cache_key,
                    response,
                )
            except Exception:
                # Cache failure must never break a valid AI response,
                # but it must be observable in logs.
                import logging as _logging
                _logging.getLogger(__name__).warning(
                    "ResponsePipeline: cache write failed for user %s "
                    "(key truncated for safety)",
                    user_id,
                )

        return {
            "response": response,
            "cached": False,
            "provider": provider,
        }