from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from database.db import (
    get_all_users,
    get_all_users_info,
    get_user_info,
    update_user_plan,
    get_user_message_count,
    get_ban_reason,
    get_plan_counts,
    get_active_subscription_count,
    ban_user,
    unban_user,
)

from services.billing.subscription_service import (
    create_subscription,
    cancel_subscription,
    get_subscription,
)

from services.billing.usage_service import UsageService


def _admin_menu_button():
    return InlineKeyboardButton("🏠 پنل مدیریت", callback_data="admin")


async def handle_users_callback(update, context, data):
    query = update.callback_query

    if data == "users":
        all_users = get_all_users()
        users = get_all_users_info(limit=10)
        keyboard = []
        for row in users:
            user_id = row[0]
            label = row[1] or row[2] or str(user_id)
            keyboard.append([
                InlineKeyboardButton(
                    f"{label} ({user_id})",
                    callback_data=f"user_info:{user_id}",
                )
            ])

        if not keyboard:
            await query.edit_message_text(
                "👥 هیچ کاربری ثبت نشده است.",
                reply_markup=InlineKeyboardMarkup([[_admin_menu_button()]]),
            )
            return True

        keyboard.append([InlineKeyboardButton("📊 آمار کامل", callback_data="stats")])
        keyboard.append([_admin_menu_button()])
        await query.edit_message_text(
            f"👥 کاربران ثبت‌شده: {len(all_users)}\n\nکاربر موردنظر را انتخاب کنید:",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return True

    if data == "subscription":
        counts = get_plan_counts()
        active = get_active_subscription_count()
        users = get_all_users_info(limit=10)
        text = (
            "💳 مدیریت اشتراک‌ها\n\n"
            f"کل کاربران: {len(get_all_users())}\n"
            f"Free: {counts.get('free', 0)}\n"
            f"Pro: {counts.get('pro', 0)}\n"
            f"Ultra: {counts.get('ultra', 0)}\n"
            f"اشتراک فعال: {active}\n\n"
            "برای مدیریت یک کاربر انتخاب کنید:"
        )
        keyboard = []
        for row in users:
            user_id = row[0]
            label = row[1] or row[2] or str(user_id)
            keyboard.append([InlineKeyboardButton(label, callback_data=f"user_info:{user_id}")])
        keyboard.append([_admin_menu_button()])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if data.startswith("user_info:"):
        try:
            target_user_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.edit_message_text("شناسه کاربر نامعتبر است.")
            return True

        user_info = get_user_info(target_user_id)
        if not user_info:
            await query.edit_message_text("کاربری با این شناسه پیدا نشد.")
            return True

        subscription = get_subscription(target_user_id)
        usage = UsageService.get_user_usage(target_user_id)
        messages_count = get_user_message_count(target_user_id)
        ban_info = get_ban_reason(target_user_id)
        banned = bool(ban_info.get("reason"))

        text = (
            "👤 اطلاعات کاربر\n"
            f"• شناسه: {user_info[0]}\n"
            f"• نام کاربری: @{user_info[1] if user_info[1] else 'ندارد'}\n"
            f"• نام: {user_info[2] or 'ندارد'}\n"
            f"• طرح فعلی: {user_info[6] or 'free'}\n"
            f"• پیام‌ها: {messages_count}\n"
            f"• مصرف امروز: {usage.get('messages', 0)} پیام، {usage.get('images', 0)} تصویر\n"
            f"• اشتراک: {subscription['status']} ({subscription['plan']})\n"
            f"• بن: {'مسدود' if banned else 'فعال'}"
        )

        ban_label = "✅ رفع بن" if banned else "🚫 بن کاربر"
        keyboard = [
            [
                InlineKeyboardButton("🟢 Free", callback_data=f"set_plan:{target_user_id}:free"),
                InlineKeyboardButton("⚡ Pro", callback_data=f"set_plan:{target_user_id}:pro"),
                InlineKeyboardButton("🚀 Ultra", callback_data=f"set_plan:{target_user_id}:ultra"),
            ],
            [InlineKeyboardButton("❌ لغو اشتراک", callback_data=f"cancel_subscription:{target_user_id}"),
             InlineKeyboardButton(ban_label, callback_data=f"toggle_ban:{target_user_id}")],
            [InlineKeyboardButton("🔙 کاربران", callback_data="users")],
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if data.startswith("set_plan:"):
        parts = data.split(":")
        if len(parts) != 3 or parts[2] not in {"free", "pro", "ultra"}:
            await query.edit_message_text("درخواست نامعتبر است.")
            return True
        target_user_id = int(parts[1])
        selected_plan = parts[2]
        update_user_plan(target_user_id, selected_plan)
        if selected_plan == "free":
            cancel_subscription(target_user_id)
        else:
            create_subscription(target_user_id, selected_plan, 30)
        await query.edit_message_text(
            f"✅ طرح {selected_plan.upper()} برای کاربر تنظیم شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 اطلاعات کاربر", callback_data=f"user_info:{target_user_id}")],
                [InlineKeyboardButton("🏠 پنل مدیریت", callback_data="admin")],
            ]),
        )
        return True

    if data.startswith("cancel_subscription:"):
        target_user_id = int(data.split(":", 1)[1])
        cancel_subscription(target_user_id)
        update_user_plan(target_user_id, "free")
        await query.edit_message_text(
            "✅ اشتراک لغو شد و کاربر Free شد.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 اطلاعات کاربر", callback_data=f"user_info:{target_user_id}")],
                [InlineKeyboardButton("🏠 پنل مدیریت", callback_data="admin")],
            ]),
        )
        return True

    if data.startswith("toggle_ban:"):
        target_user_id = int(data.split(":", 1)[1])
        if get_ban_reason(target_user_id).get("reason"):
            unban_user(target_user_id)
            message = "✅ کاربر از بن خارج شد."
        else:
            ban_user(target_user_id, "مسدود شده توسط ادمین")
            message = "🚫 کاربر مسدود شد."
        await query.edit_message_text(
            message,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👤 اطلاعات کاربر", callback_data=f"user_info:{target_user_id}")],
                [InlineKeyboardButton("🏠 پنل مدیریت", callback_data="admin")],
            ]),
        )
        return True

    return False
