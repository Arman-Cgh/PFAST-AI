from telegram import Update
from telegram.ext import ContextTypes

from database.db import get_memories, get_profile as get_user_profile
from services.billing.plan_service import get_user_limits, get_user_plan
from services.billing.subscription_service import get_subscription


def build_profile_text(user_id: int) -> str:
    profile_row = get_user_profile(user_id)
    memories = dict(get_memories(user_id))
    plan_name = get_user_plan(user_id)
    subscription = get_subscription(user_id)

    text = "👤 پروفایل شما:\n\n"

    if profile_row:
        text += f"• نام: {profile_row[1] or profile_row[2] or 'ندارد'}\n"
        text += f"• شناسه: {user_id}\n"
        text += f"• طرح فعلی: {plan_name}\n"
        text += f"• اشتراک: {subscription['status']} ({subscription['plan']})\n"
    else:
        text += f"• شناسه: {user_id}\n"

    if memories:
        text += "\nاطلاعات ذخیره‌شده:\n"
        for key, value in memories.items():
            text += f"• {key}: {value}\n"
    else:
        text += "\nهنوز اطلاعاتی از شما ذخیره نشده."

    return text


async def profile(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    user_id = update.effective_user.id
    await update.message.reply_text(
        build_profile_text(user_id)
    )