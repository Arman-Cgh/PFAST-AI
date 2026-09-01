import os

from dotenv import load_dotenv


BASE_DIR = os.path.dirname(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

load_dotenv(
    os.path.join(
        BASE_DIR,
        ".env",
    )
)


# ==========================
# AI Provider
# ==========================

AI_PROVIDER = os.getenv(
    "AI_PROVIDER",
    "groq",
).strip().lower()


# ==========================
# API Keys
# ==========================

GROQ_API_KEY = os.getenv(
    "GROQ_API_KEY",
    "",
).strip()

OPENROUTER_API_KEY = os.getenv(
    "OPENROUTER_API_KEY",
    "",
).strip()

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
).strip()

TABITOKEN_KEYS = [
    key.strip()
    for key in os.getenv(
        "TABITOKEN_KEYS",
        "",
    ).split(",")
    if key.strip()
]


# ==========================
# Base URLs
# ==========================

GROQ_BASE_URL = os.getenv(
    "GROQ_BASE_URL",
    "https://api.groq.com/openai/v1",
).strip()

OPENROUTER_BASE_URL = os.getenv(
    "OPENROUTER_BASE_URL",
    "https://openrouter.ai/api/v1",
).strip()

TABITOKEN_BASE_URL = os.getenv(
    "TABITOKEN_BASE_URL",
    "https://tabitoken.com/v1",
).strip()


# ==========================
# Models
# ==========================

GROQ_MODEL = os.getenv(
    "GROQ_MODEL",
    "llama-3.3-70b-versatile",
).strip()

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "deepseek/deepseek-chat-v3.1",
).strip()

TABITOKEN_MODEL = os.getenv(
    "TABITOKEN_MODEL",
    "claude-opus-4-8",
).strip()


# ==========================
# Active Provider Config
# ==========================

if AI_PROVIDER == "tabitoken":
    AI_API_KEY = TABITOKEN_KEYS
    AI_BASE_URL = TABITOKEN_BASE_URL
    AI_MODEL = TABITOKEN_MODEL

elif AI_PROVIDER == "openrouter":
    AI_API_KEY = OPENROUTER_API_KEY
    AI_BASE_URL = OPENROUTER_BASE_URL
    AI_MODEL = OPENROUTER_MODEL

elif AI_PROVIDER == "groq":
    AI_API_KEY = GROQ_API_KEY
    AI_BASE_URL = GROQ_BASE_URL
    AI_MODEL = GROQ_MODEL

else:
    raise ValueError(
        f"Unsupported AI_PROVIDER: {AI_PROVIDER}"
    )


# ==========================
# Telegram
# ==========================

TELEGRAM_TOKEN = os.getenv(
    "TELEGRAM_TOKEN",
    "",
).strip()


# ==========================
# Bot
# ==========================

BOT_NAME = os.getenv(
    "BOT_NAME",
    "PFAST_AI",
).strip()

BOT_CREATOR = os.getenv(
    "BOT_CREATOR",
    "@whocareit",
).strip()


# ==========================
# AI Settings
# ==========================

AI_MAX_TOKENS = int(os.getenv("AI_MAX_TOKENS", "1200"))
MAX_TOKENS = AI_MAX_TOKENS

AI_TEMPERATURE = float(os.getenv("AI_TEMPERATURE", "0.8"))
TEMPERATURE = AI_TEMPERATURE

AI_PROVIDER_TIMEOUT = float(os.getenv("AI_PROVIDER_TIMEOUT", "30.0"))

SHORT_MEMORY_LIMIT = 20

LONG_MEMORY_ENABLED = True


# ==========================
# Personality
# ==========================

SYSTEM_PROMPT = """
تو PFAST_AI هستی.

یک دستیار هوشمند شخصی مبتنی بر هوش مصنوعی هستی.
همیشه فارسی روان و طبیعی صحبت کن.
از اطلاعات حافظه و زمینه گفتگو در صورت مرتبط بودن استفاده کن.
اگر چیزی را نمی‌دانی، حدس نزن و صادقانه بگو.
پاسخ‌ها روشن، کاربردی و تا حد ممکن مستقیم باشند.
برای کدنویسی و متن فنی، ساختار مناسب و دقیق ارائه کن.
Markdown را فقط زمانی استفاده کن که به خوانایی یا نمایش کد کمک کند.
"""