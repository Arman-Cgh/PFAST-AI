from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import (
    get_ban_reason,
    ban_user,
    unban_user,
    get_all_users_info,
)


def toggle_user_ban(user_id: int):
    ban_info = get_ban_reason(user_id)
    if ban_info.get("reason"):
        unban_user(user_id)
        return {"success": True, "message": "✅ کاربر از حالت بن خارج شد."}

    ban_user(user_id, "مسدود شده توسط ادمین")
    return {"success": True, "message": "🚫 کاربر مسدود شد."}


async def handle_ban_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
):
    query = update.callback_query

    if data == "ban_user":
        users = get_all_users_info(limit=30)
        keyboard = []
        for row in users:
            user_id = row[0]
            label = row[1] or row[2] or str(user_id)
            ban_info = get_ban_reason(user_id)
            state = "🔓 آزاد" if ban_info.get("reason") else "🚫 بن"
            keyboard.append([InlineKeyboardButton(
                f"{label} ({user_id}) {state}",
                callback_data=f"toggle_ban:{user_id}",
            )])

        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="admin")])
        await query.edit_message_text(
            "🚫 مدیریت بن\n\nکاربر موردنظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data.startswith("toggle_ban:"):
        try:
            target_user_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.edit_message_text("شناسه کاربر نامعتبر است.")
            return True

        result = toggle_user_ban(target_user_id)
        await query.edit_message_text(
            result["message"],
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 مدیریت بن", callback_data="ban_user")],
                [InlineKeyboardButton("🏠 پنل مدیریت", callback_data="admin")],
            ]),
        )
        return True

    return False
