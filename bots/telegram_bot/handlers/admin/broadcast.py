from telegram import Update
from telegram.ext import ContextTypes

from database.db import (
    set_admin_action,
    clear_admin_action,
    get_all_users,
)


async def handle_broadcast_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
):
    query = update.callback_query
    user_id = query.from_user.id

    if data == "broadcast":
        set_admin_action(user_id, "broadcast")
        await query.edit_message_text(
            "📢 حالت ارسال همگانی فعال شد.\n\n"
            "حالا پیام متنی، عکس، ویدیو یا فایل موردنظر را ارسال کنید.\n"
            "برای لغو: /admin"
        )
        return True

    if data == "cancel_broadcast":
        clear_admin_action(user_id)
        await query.edit_message_text("❌ ارسال همگانی لغو شد.")
        return True

    return False


async def send_broadcast(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> bool:
    message = update.message
    if not message:
        return False

    admin_id = update.effective_user.id
    users = get_all_users()
    success = 0
    failure = 0
    first_error = ""

    for chat_id in users:
        try:
            await context.bot.copy_message(
                chat_id=chat_id,
                from_chat_id=message.chat_id,
                message_id=message.message_id,
            )
            success += 1
        except Exception as exc:
            failure += 1
            if not first_error:
                first_error = str(exc)

    clear_admin_action(admin_id)

    result = (
        f"📢 پیام همگانی ارسال شد.\n"
        f"✅ موفق: {success}\n"
        f"❌ ناموفق: {failure}"
    )
    if first_error and failure:
        result += f"\n\nاولین خطا: {first_error[:300]}"

    await message.reply_text(result)
    return True
