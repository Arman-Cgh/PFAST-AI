import os

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(
    os.path.abspath(__file__)
)

load_dotenv(
    os.path.join(
        BASE_DIR,
        ".env",
    )
)


# ==========================
# AI
# ==========================

AI_API_KEY = os.getenv(
    "AI_API_KEY",
    "",
).strip()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
).strip()

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    AI_API_KEY,
).strip()

TOKENFAUCET_API_KEY = os.getenv(
    "TOKENFAUCET_API_KEY",
    "",
).strip()

GEMINI_API_KEY = os.getenv(
    "GEMINI_API_KEY",
    "",
).strip()


# ==========================
# Telegram
# ==========================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "",
).strip()

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    TELEGRAM_TOKEN,
).strip()


# ==========================
# Bot
# ==========================

BOT_NAME = os.getenv(
    "BOT_NAME",
    "PFAST_AI",
).strip()

BOT_USERNAME = (
    os.getenv(
        "BOT_USERNAME",
        "",
    )
    .strip()
    .lstrip("@")
)

BOT_CREATOR = os.getenv(
    "BOT_CREATOR",
    "@whocareit",
).strip()


# ==========================
# Admin
# ==========================

ADMIN_ID_RAW = os.getenv(
    "ADMIN_ID",
    "5383969883",
).strip()

try:
    ADMIN_ID = int(ADMIN_ID_RAW)
except ValueError:
    ADMIN_ID = 5383969883

ADMIN_IDS_RAW = os.getenv(
    "ADMIN_IDS",
    "",
).strip()

ADMIN_IDS = {ADMIN_ID}

if ADMIN_IDS_RAW:
    for aid in ADMIN_IDS_RAW.split(","):
        aid = aid.strip()
        if aid.isdigit():
            ADMIN_IDS.add(int(aid))


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS