from services.ai.config import (
    GROQ_MODEL,
    OPENROUTER_MODEL,
    TABITOKEN_MODEL,
)


class ModelRouter:

    MODELS = {
        "groq": {
            "chat": GROQ_MODEL,
            "code": GROQ_MODEL,
            "memory": GROQ_MODEL,
            "task": None,
            "vision": GROQ_MODEL,
        },
        "openrouter": {
            "chat": OPENROUTER_MODEL,
            "code": OPENROUTER_MODEL,
            "memory": OPENROUTER_MODEL,
            "task": None,
            "vision": OPENROUTER_MODEL,
        },
        "tabitoken": {
            "chat": TABITOKEN_MODEL,
            "code": TABITOKEN_MODEL,
            "memory": TABITOKEN_MODEL,
            "task": None,
            "vision": TABITOKEN_MODEL,
        },
    }

    @classmethod
    def select(
        cls,
        provider_name,
        intent,
    ):
        provider_name = (
            str(provider_name or "groq")
            .strip()
            .lower()
        )

        intent = (
            str(intent or "chat")
            .strip()
            .lower()
        )

        provider_models = cls.MODELS.get(
            provider_name
        )

        if not provider_models:
            provider_models = cls.MODELS["groq"]

        return provider_models.get(
            intent,
            provider_models["chat"],
        )