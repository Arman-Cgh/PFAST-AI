from openai import AsyncOpenAI

from .base import AIProvider

from services.ai.config import (
    GROQ_API_KEY,
    GROQ_BASE_URL,
    AI_MODEL,
    MAX_TOKENS,
    TEMPERATURE
)

from core.logger import logger


class GroqProvider(AIProvider):


    def __init__(self):

        self.client = AsyncOpenAI(

            api_key=GROQ_API_KEY,

            base_url=GROQ_BASE_URL

        )



    async def generate(

        self,

        messages:list,

        model:str=None

    ):


        try:


            response = await self.client.chat.completions.create(

                model=model or AI_MODEL,

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


        except Exception as e:
            logger.error(
                "Groq provider error: %s",
                type(e).__name__,
            )
            raise