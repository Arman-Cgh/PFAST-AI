import json
import re

from services.ai.model_router import ModelRouter
from core.logger import logger


class InformationExtractor:

    def __init__(
        self,
        config=None,
    ):
        self.config = config

    async def extract(
        self,
        user_id: int,
        user_message: str,
        assistant_response: str = "",
        provider=None,
        provider_name=None,
    ):
        if provider is None:
            return {}

        return await extract_memory(
            provider=provider,
            provider_name=provider_name,
            user_id=user_id,
            user_message=user_message,
            assistant_response=assistant_response,
        )


def _clean_memory(
    memory: dict,
):
    if not isinstance(memory, dict):
        return {}

    allowed = {
        "name",
        "job",
        "interests",
        "location",
        "preferences",
    }

    cleaned = {}

    for key, value in memory.items():

        key = str(
            key
        ).strip().lower()

        if key not in allowed:
            continue

        if value is None:
            continue

        if isinstance(value, list):

            value = ", ".join(
                map(str, value)
            )

        value = str(
            value
        ).strip()

        if not value:
            continue

        if len(value) > 100:
            continue

        cleaned[key] = value

    return cleaned


def _clean_state(
    state: dict,
):
    if not isinstance(state, dict):
        return {}

    return {
        str(key): value
        for key, value in state.items()
        if value is not None
    }


async def extract_memory(
    provider,
    provider_name,
    user_id: int,
    user_message: str,
    assistant_response: str,
):
    prompt = f"""
Extract only permanent useful user information.

Return ONLY valid JSON.

Format:

{{
    "memory": {{}},
    "state": {{}}
}}

Rules:

- Do not save temporary requests.
- Do not save conversation content.
- Do not save guesses.
- Save only permanent user facts.
- If there is no permanent information, return empty objects.

Allowed memory:

name
job
interests
location
preferences

User:

{user_message}

Assistant:

{assistant_response}
"""

    messages = [
        {
            "role": "user",
            "content": prompt,
        }
    ]

    try:

        # ProviderManager
        if hasattr(
            provider,
            "get_model",
        ) and hasattr(
            provider,
            "generate",
        ):

            result = await provider.generate(
                messages=messages,
                intent="memory",
            )

            if isinstance(
                result,
                dict,
            ):
                response = result.get(
                    "text",
                    "",
                )
            else:
                response = result

        # Raw provider compatibility
        else:

            model = ModelRouter.select(
                provider_name,
                "memory",
            )

            try:

                response = await provider.generate(
                    messages,
                    model=model,
                )

            except TypeError:

                response = await provider.generate(
                    messages,
                )

            if isinstance(
                response,
                dict,
            ):
                response = response.get(
                    "text",
                    "",
                )

        if not response:
            return {}

        cleaned = re.sub(
            r"```(?:json)?",
            "",
            str(response),
            flags=re.IGNORECASE,
        ).strip()

        # Remove trailing code fence.
        cleaned = cleaned.replace(
            "```",
            "",
        ).strip()

        match = re.search(
            r"\{.*\}",
            cleaned,
            re.DOTALL,
        )

        if not match:

            logger.warning(
                "Invalid extractor JSON"
            )

            return {}

        data = json.loads(
            match.group()
        )

        return {
            "memory": _clean_memory(
                data.get(
                    "memory",
                    {},
                )
            ),
            "state": _clean_state(
                data.get(
                    "state",
                    {},
                )
            ),
        }

    except Exception as e:

        logger.exception(
            "Extractor error: %s",
            e,
        )

        return {}