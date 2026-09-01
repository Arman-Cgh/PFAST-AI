from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_ID, is_admin
from database.mandatory_join import get_display_name, get_mandatory_join_message, get_missing_channels


async def check_mandatory_join(bot, user_id):
    missing = await get_missing_channels(bot, user_id)
    if not missing:
        return True

    keyboard = []
    for channel in missing:
        url = channel.get("invite_link")
        if not url and channel.get("username"):
            url = f"https://t.me/{channel['username'].lstrip('@')}"
        if url:
            keyboard.append([
                InlineKeyboardButton(
                    f"📢 عضویت در {get_display_name(channel)}",
                    url=url,
                )
            ])
    keyboard.append([
        InlineKeyboardButton("✅ بررسی عضویت", callback_data="check_mandatory_join")
    ])
    return InlineKeyboardMarkup(keyboard)


async def require_mandatory_join(update, context):
    user = update.effective_user
    if not user:
        return True
    if is_admin(user.id):
        return True

    bot = getattr(context, "bot", None)
    if bot is None:
        # Test/fallback contexts may not expose a Telegram bot.
        return True

    markup = await check_mandatory_join(bot, user.id)
    if markup is True:
        return True

    text = get_mandatory_join_message()
    if update.message:
        await update.message.reply_text(text, reply_markup=markup)
    elif update.callback_query:
        await update.callback_query.answer(
            "ابتدا در کانال‌های اجباری عضو شوید.",
            show_alert=True,
        )
        await update.callback_query.message.reply_text(text, reply_markup=markup)
    return False
