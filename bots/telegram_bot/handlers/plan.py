from telegram import Update
from telegram.ext import ContextTypes

from telegram import Update
from telegram.ext import ContextTypes

from services.billing.plan_service import get_user_limits, get_user_plan
from services.billing.usage_service import UsageService
from services.billing.subscription_service import get_subscription

# Human-friendly display names for plan keys
DISPLAY_NAMES = {
    "daily_messages": "💬 پیام روزانه",
    "daily_images": "🖼 درخواست تصویر",
    "daily_technical_questions": "🧠 سوال فنی",
    "cooldown_seconds": "⏱ فاصله ارسال",
}


def _human_key(key: str) -> str:
    if key in DISPLAY_NAMES:
        return DISPLAY_NAMES[key]
    # fallback: convert snake_case to words
    return key.replace("_", " ").capitalize()


def build_plan_text(user_id: int) -> str:
    plan_name = get_user_plan(user_id)
    limits = get_user_limits(user_id)
    usage = UsageService.get_user_usage(user_id)
    subscription = get_subscription(user_id)

    text = f"📦 طرح شما: {plan_name}\n\n"

    # Show each available limit in a friendly way
    for key, val in limits.items():
        # skip non-limit fields if any
        if key in ("id", "name"):
            continue
        human = _human_key(key)
        # show usage if we know usage mapping
        if key == "daily_messages":
            used = usage.get("messages", 0)
            text += f"• {human}: {used} / {val}\n"
        elif key == "daily_images":
            used = usage.get("images", 0)
            text += f"• {human}: {used} / {val}\n"
        elif key == "daily_technical_questions":
            used = usage.get("code_requests", 0)
            text += f"• {human}: {used} / {val}\n"
        else:
            # generic display
            display_val = val if val is not None else "(خالی)"
            text += f"• {human}: {display_val}\n"

    text += "\n"

    if subscription.get("is_active"):
        text += (
            f"🔔 اشتراک فعال است.\n"
            f"• تاریخ شروع: {subscription.get('start_date')}\n"
            f"• پایان: {subscription.get('end_date')}\n"
            f"• روزهای باقی‌مانده: {subscription.get('days_remaining')}\n"
            "\n"
        )
    elif subscription.get("status") in ["expired", "cancelled"]:
        text += (
            f"🔔 اشتراک شما {subscription.get('status')} شده است.\n"
            f"• طرح قبلی: {subscription.get('plan')}\n"
            "\n"
        )

    text += (
        "برای ارتقا به طرح‌های حرفه‌ای با ادمین تماس بگیرید.\n"
        "اگر می‌خواهید طرح را تغییر دهید، از ادمین بخواهید روی حساب شما تنظیم کند."
    )
    return text


async def plan_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    await update.message.reply_text(
        build_plan_text(user_id)
    )
