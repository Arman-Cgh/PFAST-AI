from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes


from database.db import (
    set_broadcast_message,
    get_all_users,
    get_all_users_info,
    get_user_info,
    get_total_messages,
    get_total_memories,
    get_total_cached_questions,
    set_admin_action,
    update_user_plan,
    get_plan_counts,
    get_active_subscription_count,
    get_user_message_count,
    get_user_message_history,
    get_ban_reason,
    get_plan_prices,
    set_plan_price,
    get_referral_settings,
    set_referral_settings
)
from services.billing.plan_service import get_all_plans, get_plan, update_plan
from services.billing.subscription_service import (
    create_subscription,
    cancel_subscription,
    get_subscription
)

from services.billing.payment_service import (
    approve_payment,
    reject_payment,
)
from services.billing.usage_service import UsageService
from database.db import get_all_payment_requests
from handlers.admin.payments import handle_payments_callback
from handlers.admin.plans import handle_plans_callback
from handlers.admin.broadcast import start_broadcast
from handlers.admin.ban import (
    toggle_user_ban,
    activate_ban_mode,
)
from handlers.admin.users import handle_users_callback
ADMIN_ID = 5383969883


async def admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    query = update.callback_query

    await query.answer()


    user_id = query.from_user.id


    if user_id != ADMIN_ID:

        await query.edit_message_text(
            "⛔ دسترسی ندارید."
        )

        return


    data = query.data
    handled = await handle_payments_callback(
        update,
        context,
        data
    )

    if handled:
        return
    
    handled = await handle_plans_callback(
        update,
        context,
        data
    )

    if handled:
        return
    
    handled = await handle_users_callback(
        update,
        context,
        data
    )

    if handled:
        return


    # ==========================
    # Users
    # ==========================

    if data == "users":

        all_users = get_all_users()
        users = get_all_users_info(limit=10)
        keyboard = []

        for user_row in users:
            user_id_value = user_row[0]
            username = user_row[1] or user_row[2] or str(user_id_value)
            keyboard.append([
                InlineKeyboardButton(
                    f"{username}",
                    callback_data=f"user_info:{user_id_value}"
                )
            ])

        if not keyboard:
            await query.edit_message_text(
                "👥 هیچ کاربری ثبت نشده است."
            )
            return

        keyboard.append([
            InlineKeyboardButton(
                "📊 آمار کامل",
                callback_data="stats"
            )
        ])

        await query.edit_message_text(
            f"👥 کاربران ثبت‌شده: {len(all_users)}\n"
            "برای مشاهده جزئیات کاربر، روی آیدی او کلیک کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return


    if data.startswith("user_info:"):
        try:
            target_user_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.edit_message_text(
                "شناسه کاربر معتبر نیست."
            )
            return

        user_info = get_user_info(target_user_id)
        if not user_info:
            await query.edit_message_text(
                "کاربری با این شناسه پیدا نشد."
            )
            return

        subscription = get_subscription(target_user_id)
        usage = UsageService.get_user_usage(target_user_id)
        messages_count = get_user_message_count(target_user_id)
        history = get_user_message_history(target_user_id, limit=5)
        ban_info = get_ban_reason(target_user_id)

        text = (
            f"👤 اطلاعات کاربر:\n"
            f"• شناسه: {user_info[0]}\n"
            f"• نام کاربری: @{user_info[1] if user_info[1] else 'ندارد'}\n"
            f"• نام: {user_info[2] or 'ندارد'}\n"
            f"• نام مستعار: {user_info[3] or 'ندارد'}\n"
            f"• بیو: {user_info[4] or 'ندارد'}\n"
            f"• علاقه‌مندی‌ها: {user_info[5] or 'ندارد'}\n"
            f"• طرح فعلی: {user_info[6] or 'free'}\n"
            f"• پیام‌های ثبت‌شده: {messages_count}\n"
            f"• مصرف امروز: {usage['messages']} پیام، {usage['images']} تصویر\n"
            f"• اشتراک: {subscription['status']} ({subscription['plan']})\n"
            f"• وضعیت بن: {'مسدود' if ban_info.get('reason') else 'فعال'}\n"
        )

        if subscription.get("is_active"):
            text += (
                f"• شروع: {subscription['start_date']}\n"
                f"• پایان: {subscription['end_date']}\n"
                f"• روزهای باقی‌مانده: {subscription['days_remaining']}\n"
            )

        if history:
            text += "\nپیام‌های اخیر:\n"
            for role, message in history:
                display_role = "کاربر" if role == "user" else "ربات"
                text += f"• [{display_role}] {message}\n"

        keyboard = [
            [
                InlineKeyboardButton(
                    "🟢 Free",
                    callback_data=f"set_plan:{target_user_id}:free"
                ),
                InlineKeyboardButton(
                    "⚡ Pro",
                    callback_data=f"set_plan:{target_user_id}:pro"
                ),
                InlineKeyboardButton(
                    "🚀 Ultra",
                    callback_data=f"set_plan:{target_user_id}:ultra"
                )
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو اشتراک",
                    callback_data=f"cancel_subscription:{target_user_id}"
                ),
                InlineKeyboardButton(
                    "🚫 بن/آزادسازی",
                    callback_data=f"toggle_ban:{target_user_id}"
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="users"
                )
            ]
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )

        return

    if data.startswith("set_plan:"):
        parts = data.split(":")
        if len(parts) != 3:
            await query.edit_message_text(
                "درخواست نامعتبر است."
            )
            return

        try:
            target_user_id = int(parts[1])
        except ValueError:
            await query.edit_message_text(
                "شناسه کاربر نامعتبر است."
            )
            return

        selected_plan = parts[2]
        if selected_plan not in ["free", "pro", "ultra"]:
            await query.edit_message_text(
                "طرح انتخابی معتبر نیست."
            )
            return

        update_user_plan(target_user_id, selected_plan)
        if selected_plan == "free":
            cancel_subscription(target_user_id)
            await query.edit_message_text(
                f"✅ طرح کاربر به Free بازگشت و اشتراک لغو شد."
            )
        else:
            create_subscription(target_user_id, selected_plan, 30)
            await query.edit_message_text(
                f"✅ طرح {selected_plan} برای کاربر فعال شد. اشتراک ۳۰ روزه تنظیم شد."
            )

        return

    if data.startswith("cancel_subscription:"):
        try:
            target_user_id = int(data.split(":", 1)[1])
        except (ValueError, IndexError):
            await query.edit_message_text(
                "شناسه کاربر نامعتبر است."
            )
            return

        cancel_subscription(target_user_id)
        update_user_plan(target_user_id, "free")

        await query.edit_message_text(
            "✅ اشتراک کاربر لغو شد و طرح به Free بازگشت."
        )

        return

    if data == "subscription":
        plan_counts = get_plan_counts()
        active_subscriptions = get_active_subscription_count()
        total_users = len(get_all_users())

        await query.edit_message_text(
            f"💳 وضعیت اشتراک‌ها:\n"
            f"• کل کاربران: {total_users}\n"
            f"• کاربران Free: {plan_counts.get('free', 0)}\n"
            f"• کاربران Pro: {plan_counts.get('pro', 0)}\n"
            f"• کاربران Ultra: {plan_counts.get('ultra', 0)}\n"
            f"• اشتراک‌های فعال: {active_subscriptions}\n\n"
            "برای مدیریت هر کاربر، دکمه کاربران را بزنید.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("👥 کاربران", callback_data="users")],
                [InlineKeyboardButton("📊 آمار", callback_data="stats")]
            ])
        )

        return

    if data.startswith("toggle_ban:"):

        target_user_id = int(
            data.split(":", 1)[1]
        )

        result = toggle_user_ban(
            target_user_id
        )

        await query.edit_message_text(
            result["message"]
        )

        return

    # ==========================
    # Ban user
    # ==========================

    if data == "ban_user":

        message = activate_ban_mode(
            user_id
        )

    await query.edit_message_text(
        message
    )

    return




    # ==========================
    # Broadcast
    # ==========================
    await start_broadcast(update, context)
    return


    # ==========================
    # Image generation
    # ==========================

    if data == "image":

        set_admin_action(
            user_id,
            "image"
        )

        await query.edit_message_text(
            "🖼 ساخت عکس فعال شد.\n\n"
            "لطفاً متن یا توضیح تصویر را ارسال کن."
        )

        return


    # ==========================
    # Technical question
    # ==========================

    if data == "technical":

        set_admin_action(
            user_id,
            "technical"
        )

        await query.edit_message_text(
            "🧠 حالت دانش فنی فعال شد.\n\n"
            "حالا سوال یا مسئله فنی را ارسال کن."
        )

        return


    # ==========================
    # Plans management (Admin)
    # ==========================

    if data == "manage_plans":
        plans = get_all_plans()
        text = "⚙️ مدیریت پلن‌ها:\n"
        for plan_name in ["free", "pro", "ultra"]:
            plan_exists = "✅" if plans.get(plan_name) else "❌"
            text += f"• {plan_name.upper()} {plan_exists}\n"

        keyboard = [
            [
                InlineKeyboardButton("Free", callback_data="manage_plans:free"),
                InlineKeyboardButton("Pro", callback_data="manage_plans:pro"),
                InlineKeyboardButton("Ultra", callback_data="manage_plans:ultra"),
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="users")]
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("manage_plans:"):
        plan_name = data.split(":", 1)[1]
        plan = get_plan(plan_name)
        if not plan:
            await query.edit_message_text("پلن مورد نظر یافت نشد.")
            return

        text = f"⚙️ تنظیمات پلن {plan_name.upper()}:\n\n"
        # show keys (except id and name)
        for key, val in plan.items():
            if key in ("id", "name"):
                continue
            display_val = val if val is not None else "(خالی)"
            text += f"• {key}: {display_val}\n"

        keyboard = []
        row = []
        for key in plan.keys():
            if key in ("id", "name"):
                continue
            row.append(InlineKeyboardButton(f"✏️ {key}", callback_data=f"edit_plan:{plan_name}:{key}"))
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="manage_plans")])

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("edit_plan:"):
        # format: edit_plan:{plan}:{key}
        parts = data.split(":", 2)
        if len(parts) != 3:
            await query.edit_message_text("درخواست نامعتبر است.")
            return
        plan_name = parts[1]
        key = parts[2]
        # set admin action so next admin message is treated as the new value
        set_admin_action(user_id, f"edit_plan_waiting:{plan_name}:{key}")
        await query.edit_message_text(
            f"✏️ مقدار جدید برای {key} در پلن {plan_name.upper()} را ارسال کنید.\n(فقط ستون‌های موجود قابل ویرایش‌اند و مقادیر عددی برای فیلدهای عددی لازم است)")
        return

    # ==========================
    # Pricing
    # ==========================

    if data == "pricing":
        prices = get_plan_prices()
        text = "💰 قیمت‌های فعلی:\n"
        for plan_name in ["pro", "ultra"]:
            plan_data = prices.get(plan_name, {"price": 0, "currency": "IRR"})
            text += f"• {plan_name.upper()}: {plan_data['price']} {plan_data['currency']}\n"

        keyboard = [
            [
                InlineKeyboardButton("⚡ Pro", callback_data="set_price:pro"),
                InlineKeyboardButton("🚀 Ultra", callback_data="set_price:ultra")
            ],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="users")]
        ]

        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    if data.startswith("set_price:"):
        plan_name = data.split(":", 1)[1]
        set_admin_action(user_id, f"set_price:{plan_name}")
        await query.edit_message_text(
            f"💰 قیمت {plan_name.upper()} را ارسال کن.\n"
            "می‌توانی عدد ساده، عدد فارسی، متن مانند ۳۰۰ هزار تومان یا حتی با اموجی هم وارد کنی."
        )
        return

    # ==========================
    # Referral settings
    # ==========================

    if data == "referral_settings":
        settings = get_referral_settings()
        set_admin_action(user_id, "set_referral_config")
        await query.edit_message_text(
            "👥 تنظیمات رفرال:\n"
            f"• حداقل دعوت: {settings['required_invites']}\n"
            f"• مدت پاداش: {settings['reward_days']} روز\n"
            f"• پلن پاداش: {settings['reward_plan'].upper()}\n\n"
            "برای تغییر، متن را به این شکل بفرست:\n"
            "3 3 pro"
        )
        return

    # ==========================
    # Stats
    # ==========================

    if data == "stats":

        users = get_all_users()
        total_messages = get_total_messages()
        total_memories = get_total_memories()
        total_cache = get_total_cached_questions()
        plan_counts = get_plan_counts()

        await query.edit_message_text(
            f"📊 آمار سیستم:\n"
            f"• کاربران ثبت‌شده: {len(users)}\n"
            f"• Free: {plan_counts.get('free', 0)}\n"
            f"• Pro: {plan_counts.get('pro', 0)}\n"
            f"• Ultra: {plan_counts.get('ultra', 0)}\n"
            f"• پیام‌های ذخیره‌شده: {total_messages}\n"
            f"• موارد حافظه: {total_memories}\n"
            f"• پاسخ‌های کش‌شده: {total_cache}"
        )

        return


    # ==========================
    # Close
    # ==========================

    if data == "close":

        await query.edit_message_text(
            "❌ پنل بسته شد."
        )

        return


    await query.edit_message_text(
        "در حال توسعه..."
    )