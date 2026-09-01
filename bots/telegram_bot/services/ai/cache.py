import hashlib
import json


class AICache:
    PROMPT_VERSION = "1"

    BYPASS_INTENTS = {
        "task",
        "memory",
        "image",
        "vision",
        "search",
    }

    CHAT_BYPASS_PATTERNS = (
        "continue",
        "continue please",
        "explain more",
        "another example",
        "why",
        "what do you mean",
        "what did we discuss",
        "what did we talk about",
        "summarize",
        "my name",
        "what is my name",
        "what am i working on",
        "what am i doing",
        "do you remember",
        "what do you remember",
        "remember",
        "save this",
        "yesterday",
        "today",
        "now",
        "current time",
        "current date",
        "profile",
        "memory",
        "history",
        "state",
        "task",
        "my project",
        "current project",
        "current goal",
        "my goal",
        "what are my goals",
        "what is my goal",
        "what is my project",
        "what project am i",
        "what am i",
        "how am i",
        "what should i",
        "should i",
        "یادم بنداز",
        "یادآوری",
        "یادآوری کن",
        "یک کار",
        "وظیفه",
        "اسم من",
        "من کی هستم",
        "درباره من",
        "یادت باشه",
        "به خاطر بسپار",
        "ادامه",
        "بیشتر توضیح بده",
        "یک مثال دیگر",
        "چرا",
        "چه منظوری داری",
        "چه چیزی رو گفتم",
        "دیروز",
        "امروز",
        "حالا",
        "فعلا",
        "آیا یادت میاد",
        "خاطره",
        "تاریخچه",
        "پروژه من",
        "هدف من",
    )

    def __init__(
        self,
        prompt_version=None,
    ):
        self.prompt_version = (
            prompt_version
            or self.PROMPT_VERSION
        )

    def _normalize_text(
        self,
        text,
    ):
        return " ".join(
            str(text or "")
            .strip()
            .lower()
            .split()
        )

    def generate_key(
        self,
        user_message,
        intent,
        model=None,
        prompt_version=None,
        prompt_payload=None,
    ):
        """
        Generate a deterministic cache key.

        For a fully-built prompt, prompt_payload is preferred
        because it captures the actual context sent to the model.
        """

        version = (
            prompt_version
            or self.prompt_version
        )

        normalized_message = (
            self._normalize_text(
                user_message
            )
        )

        if prompt_payload is not None:
            try:
                payload = json.dumps(
                    prompt_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
            except (
                TypeError,
                ValueError,
            ):
                payload = str(
                    prompt_payload
                )
        else:
            payload = normalized_message

        key_text = (
            f"{version}|"
            f"{str(intent or 'chat').strip().lower()}|"
            f"{str(model or 'unknown')}|"
            f"{payload}"
        )

        return hashlib.sha256(
            key_text.encode("utf-8")
        ).hexdigest()

    def is_cacheable(
        self,
        intent,
        user_message,
    ):
        normalized_message = (
            self._normalize_text(
                user_message
            )
        )

        if not normalized_message:
            return False

        intent = (
            str(intent or "chat")
            .strip()
            .lower()
        )

        if intent in self.BYPASS_INTENTS:
            return False

        if intent == "code":
            return True

        if intent != "chat":
            return False

        for pattern in self.CHAT_BYPASS_PATTERNS:
            if pattern in normalized_message:
                return False

        return True

    async def get(
        self,
        user_id,
        cache_key,
    ):
        """
        Persistent cache lookup.

        database.db remains the storage backend.
        """

        from database.db import (
            get_cached_answer,
        )

        return get_cached_answer(
            user_id,
            cache_key,
            prompt_version=self.prompt_version,
        )

    async def set(
        self,
        user_id,
        cache_key,
        value,
        ttl=None,
    ):
        """
        Persist a cache value.

        TTL is accepted for API compatibility. The current
        database cache implementation controls expiration.
        """

        if not value:
            return False

        from database.db import (
            save_cached_answer,
        )

        save_cached_answer(
            user_id,
            cache_key,
            value,
            prompt_version=self.prompt_version,
        )

        return True