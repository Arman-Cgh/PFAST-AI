from openai import AsyncOpenAI

from services.ai.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    OPENROUTER_MODEL,
    MAX_TOKENS,
    TEMPERATURE
)


class OpenRouterProvider:


    def __init__(self):

        self.client = AsyncOpenAI(

            api_key=OPENROUTER_API_KEY,

            base_url=OPENROUTER_BASE_URL

        )



    async def generate(

        self,

        messages,

        model: str = None

    ):


        response = await self.client.chat.completions.create(

            model=model or OPENROUTER_MODEL,

            messages=messages,

            max_tokens=MAX_TOKENS,

            temperature=TEMPERATURE

        )


        return (

            response
            .choices[0]
            .message
            .content
            .strip()

        )
