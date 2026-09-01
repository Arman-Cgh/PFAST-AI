import asyncio

from telegram import Bot

from services.ai.config import TELEGRAM_TOKEN
from handlers.user_callbacks import build_referral_message


async def main():
    bot = Bot(TELEGRAM_TOKEN)

    await bot.initialize()

    try:
        me = await bot.get_me()

        print("BOT USERNAME:", me.username)
        print()
        print(
            build_referral_message(
                777777,
                me.username,
            )
        )

    finally:
        await bot.shutdown()


if __name__ == "__main__":
    asyncio.run(main())

