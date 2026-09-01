import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import clear_admin_action, get_admin_action, set_admin_action
from database.mandatory_join import (
    add_channel,
    get_channel,
    get_channels,
    get_display_name,
    get_mandatory_join_message,
    remove_channel,
    set_channel_active,
    set_mandatory_join_message,
)
from config import ADMIN_ID, is_admin


def _main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن کانال خودی", callback_data="mandatory_add:own")],
        [InlineKeyboardButton("➕ افزودن کانال تبلیغاتی", callback_data="mandatory_add:ads")],
        [InlineKeyboardButton("✏️ تغییر متن", callback_data="mandatory_message")],
        [InlineKeyboardButton("🔄 روشن/خاموش", callback_data="mandatory_toggle")],
        [InlineKeyboardButton("🗑 حذف کانال", callback_data="mandatory_remove")],
        [InlineKeyboardButton("🔙 بازگشت", callback_data="admin")],
    ])


def _render_channels():
    channels = get_channels()
    own = sum(c["kind"] == "own" for c in channels)
    ads = sum(c["kind"] == "ads" for c in channels)
    text = (
        "🔒 مدیریت جوین اجباری\n\n"
        f"🟢 کانال‌های خودی: {own}\n"
        f"📢 کانال‌های تبلیغاتی: {ads}\n\n"
        f"📝 متن فعلی:\n{get_mandatory_join_message()}\n\n"
    )
    if not channels:
        text += "هنوز کانالی ثبت نشده است."
    else:
        text += "📋 کانال‌ها:\n"
        for c in channels:
            status = "🟢 فعال" if c["active"] else "🔴 خاموش"
            kind = "خودی" if c["kind"] == "own" else "تبلیغاتی"
            text += f"#{c['id']} | {kind} | {get_display_name(c)} | {status}\n"
    return text


async def handle_mandatory_join_callback(update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    user_id = query.from_user.id

    if data == "mandatory_join":
        await query.edit_message_text(_render_channels(), reply_markup=_main_keyboard())
        return True

    if data.startswith("mandatory_add:"):
        kind = data.split(":", 1)[1].lower()
        if kind not in {"own", "ads"}:
            await query.edit_message_text("❌ نوع کانال نامعتبر است.")
            return True
        set_admin_action(user_id, f"mandatory_add:{kind}")
        await query.edit_message_text(
            f"➕ افزودن کانال {'خودی' if kind == 'own' else 'تبلیغاتی'}\n\n"
            "کانال عمومی:\n"
            "@ChannelUsername یا https://t.me/ChannelUsername\n\n"
            "کانال خصوصی:\n"
            "chat_id | title | username | invite_link\n\n"
            "ربات باید داخل کانال دسترسی لازم برای بررسی عضویت داشته باشد."
        )
        return True

    if data == "mandatory_message":
        set_admin_action(user_id, "mandatory_message")
        await query.edit_message_text(
            "✏️ متن جدید جوین اجباری را ارسال کنید.\n\n"
            "این متن قبل از لیست کانال‌ها به کاربر نمایش داده می‌شود."
        )
        return True

    if data == "mandatory_toggle":
        channels = get_channels()
        keyboard = []
        for c in channels:
            action = "🔴 خاموش کردن" if c["active"] else "🟢 روشن کردن"
            keyboard.append([
                InlineKeyboardButton(
                    f"{action} | #{c['id']} {get_display_name(c)}",
                    callback_data=f"mandatory_toggle:{c['id']}",
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mandatory_join")])
        await query.edit_message_text(
            "کانال موردنظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data.startswith("mandatory_toggle:"):
        try:
            channel_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.edit_message_text("❌ شناسه کانال نامعتبر است.")
            return True
        channel = get_channel(channel_id)
        if not channel:
            await query.edit_message_text("❌ کانال پیدا نشد.")
            return True
        set_channel_active(channel_id, not channel["active"])
        state = "فعال" if not channel["active"] else "خاموش"
        await query.edit_message_text(
            f"✅ وضعیت کانال #{channel_id} به «{state}» تغییر کرد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 مدیریت جوین اجباری", callback_data="mandatory_join")]
            ]),
        )
        return True

    if data == "mandatory_remove":
        channels = get_channels()
        keyboard = []
        for c in channels:
            keyboard.append([
                InlineKeyboardButton(
                    f"🗑 #{c['id']} {get_display_name(c)}",
                    callback_data=f"mandatory_delete:{c['id']}",
                )
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="mandatory_join")])
        await query.edit_message_text(
            "کانال موردنظر برای حذف را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data.startswith("mandatory_delete:"):
        try:
            channel_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.edit_message_text("❌ شناسه کانال نامعتبر است.")
            return True
        if not remove_channel(channel_id):
            await query.edit_message_text("❌ کانال پیدا نشد.")
            return True
        await query.edit_message_text(
            "✅ کانال حذف شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 مدیریت جوین اجباری", callback_data="mandatory_join")]
            ]),
        )
        return True

    # User callback handles this one; admin must not consume it.
    if data == "check_mandatory_join":
        return False

    return False


async def handle_mandatory_join_message(update, context):
    user = update.effective_user
    message = update.message
    if not user or not message or not is_admin(user.id):
        return False

    action = get_admin_action(user.id)
    if not action:
        return False

    text = (message.text or "").strip()
    if not text:
        return False

    if action == "mandatory_message":
        try:
            set_mandatory_join_message(text)
        except ValueError:
            await message.reply_text("❌ متن نمی‌تواند خالی باشد.")
            return True
        clear_admin_action(user.id)
        await message.reply_text(
            "✅ متن جوین اجباری ذخیره شد.",
            reply_markup=_main_keyboard(),
        )
        return True

    if action.startswith("mandatory_add:"):
        kind = action.split(":", 1)[1]
        try:
            if "|" in text:
                parts = [p.strip() for p in text.split("|")]
                if len(parts) != 4:
                    raise ValueError("فرمت خصوصی باید ۴ بخش داشته باشد.")
                chat_id, title, username, invite_link = parts
                if not chat_id:
                    raise ValueError("chat_id خالی است.")
            else:
                value = text
                if value.startswith("https://t.me/"):
                    username = value.rstrip("/").rsplit("/", 1)[-1]
                    invite_link = value
                elif value.startswith("http://t.me/"):
                    username = value.rstrip("/").rsplit("/", 1)[-1]
                    invite_link = value
                else:
                    username = value.lstrip("@").strip()
                    invite_link = f"https://t.me/{username}"
                if not username or not re.fullmatch(r"[A-Za-z0-9_]{4,64}", username):
                    raise ValueError("لینک یا username کانال معتبر نیست.")

                chat = await context.bot.get_chat(f"@{username}")
                chat_id = str(chat.id)
                title = chat.title or username
                username = (chat.username or username).lstrip("@")
                invite_link = invite_link

            # Resolve/validate chat when possible; private channels can use the supplied id.
            try:
                if not str(chat_id).startswith("-") and str(chat_id).isdigit():
                    pass
                else:
                    await context.bot.get_chat(chat_id)
            except Exception as exc:
                raise ValueError(f"ربات نتوانست کانال را پیدا کند: {exc}")

            add_channel(kind, chat_id, title, username, invite_link)
        except Exception as exc:
            await message.reply_text(
                f"❌ کانال ذخیره نشد.\n{exc}\n\n"
                "فرمت عمومی: @ChannelUsername\n"
                "فرمت خصوصی: chat_id | title | username | invite_link"
            )
            return True

        clear_admin_action(user.id)
        await message.reply_text(
            "✅ کانال با موفقیت ثبت شد و فعال است.",
            reply_markup=_main_keyboard(),
        )
        return True

    return False
