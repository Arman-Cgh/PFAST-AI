import asyncio

from services.ai.engine import AIEngine


async def main():

    engine = AIEngine()

    result = await engine.generate_response(
        user_id=1,
        message="معماری PFAST_AI رو بررسی کن",
        use_cache=False
    )

    print("\n===== RESPONSE =====")
    print(result["response"])


if __name__ == "__main__":
    asyncio.run(main())