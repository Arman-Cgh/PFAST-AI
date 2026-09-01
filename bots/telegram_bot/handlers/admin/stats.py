from telegram import Update
from telegram.ext import ContextTypes

from database.db import (
    get_total_messages,
    get_total_memories,
    get_total_cached_questions,
    get_all_users,
    get_plan_counts,
)


def get_bot_stats():

    users = len(
        get_all_users()
    )

    messages = get_total_messages()

    return users, messages



async def handle_stats_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
):

    query = update.callback_query


    if data != "stats":
        return False


    users, messages = get_bot_stats()

    memories = get_total_memories()
    cache = get_total_cached_questions()
    plans = get_plan_counts()


    await query.edit_message_text(
        f"📊 آمار سیستم:\n\n"
        f"👥 کاربران: {users}\n"
        f"💬 پیام‌ها: {messages}\n"
        f"🧠 حافظه‌ها: {memories}\n"
        f"⚡ کش پاسخ‌ها: {cache}\n\n"
        f"🟢 Free: {plans.get('free', 0)}\n"
        f"⚡ Pro: {plans.get('pro', 0)}\n"
        f"🚀 Ultra: {plans.get('ultra', 0)}"
    )

    return True