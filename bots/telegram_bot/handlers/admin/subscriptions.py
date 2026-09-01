from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from database.db import (
    get_all_users,
    get_all_users_info,
    get_plan_counts,
    get_active_subscription_count,
    update_user_plan,
)

from services.billing.subscription_service import (
    cancel_subscription,
    create_subscription,
    get_subscription,
)

from config import ADMIN_ID, is_admin

VALID_PLANS = {
    "free",
    "pro",
    "ultra",
}

DEFAULT_DURATION_DAYS = 30


def activate_user_plan(
    user_id,
    plan_name,
    duration_days=DEFAULT_DURATION_DAYS,
):
    plan_name = str(
        plan_name or "free"
    ).strip().lower()

    if plan_name not in VALID_PLANS:
        raise ValueError(
            f"Invalid plan: {plan_name}"
        )

    duration_days = int(
        duration_days
    )

    if duration_days < 0:
        raise ValueError(
            "duration_days cannot be negative"
        )

    # Free means no active paid subscription.
    if plan_name == "free":
        cancel_subscription(
            user_id
        )

        update_user_plan(
            user_id,
            "free",
        )

        return (
            "✅ پلن کاربر به Free بازگشت "
            "و اشتراک لغو شد."
        )

    create_subscription(
        user_id,
        plan_name,
        duration_days,
    )

    update_user_plan(
        user_id,
        plan_name,
    )

    display_plan = plan_name.capitalize()

    return (
        f"✅ پلن {display_plan} "
        f"برای کاربر فعال شد. "
        f"اشتراک {duration_days} روزه تنظیم شد."
    )


def cancel_user_subscription(
    user_id,
):
    cancel_subscription(
        user_id
    )

    update_user_plan(
        user_id,
        "free",
    )

    return (
        "✅ اشتراک کاربر لغو شد "
        "و پلن به Free بازگشت."
    )


def get_user_subscription(
    user_id,
):
    return get_subscription(
        user_id
    )


def get_subscription_stats():
    plan_counts = get_plan_counts()
    active_subscriptions = (
        get_active_subscription_count()
    )
    total_users = len(
        get_all_users()
    )

    return {
        "total_users": total_users,
        "free": int(
            plan_counts.get("free", 0)
        ),
        "pro": int(
            plan_counts.get("pro", 0)
        ),
        "ultra": int(
            plan_counts.get("ultra", 0)
        ),
        "active_subscriptions": int(
            active_subscriptions
        ),
    }


def _subscription_text(
    user_id,
):
    sub = get_subscription(
        user_id
    )

    plan = str(
        sub.get(
            "plan",
            "free",
        )
    ).upper()

    status = sub.get(
        "status",
        "inactive",
    )

    start_date = (
        sub.get("start_date")
        or "ندارد"
    )

    end_date = (
        sub.get("end_date")
        or "ندارد"
    )

    days_remaining = int(
        sub.get(
            "days_remaining",
            0,
        )
        or 0
    )

    return (
        "💎 اطلاعات اشتراک\n\n"
        f"📦 پلن: {plan}\n"
        f"📌 وضعیت: {status}\n"
        f"📅 شروع: {start_date}\n"
        f"📅 پایان: {end_date}\n"
        f"⏳ روزهای باقی‌مانده: "
        f"{days_remaining}"
    )


def _user_label(
    row,
):
    user_id = row[0]

    username = (
        row[1]
        if len(row) > 1
        else ""
    )

    first_name = (
        row[2]
        if len(row) > 2
        else ""
    )

    return str(
        username
        or first_name
        or user_id
    )


def _back_to_subscriptions():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="subscription",
                )
            ],
            [
                InlineKeyboardButton(
                    "🛠 پنل مدیریت",
                    callback_data="admin",
                )
            ],
        ]
    )


def _user_subscription_keyboard(
    user_id,
):
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🟢 Free",
                    callback_data=(
                        f"set_plan:{user_id}:free"
                    ),
                ),
                InlineKeyboardButton(
                    "⚡ Pro",
                    callback_data=(
                        f"set_plan:{user_id}:pro"
                    ),
                ),
                InlineKeyboardButton(
                    "🚀 Ultra",
                    callback_data=(
                        f"set_plan:{user_id}:ultra"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    "❌ لغو اشتراک",
                    callback_data=(
                        f"cancel_subscription:{user_id}"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    "🔙 لیست اشتراک‌ها",
                    callback_data="subscription",
                )
            ],
        ]
    )


async def handle_subscriptions_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
):
    query = update.callback_query

    if query is None:
        return False

    user = query.from_user

    if user is None or not is_admin(user.id):
        await query.edit_message_text(
            "⛔ دسترسی ندارید."
        )
        return True

    # ==========================
    # Subscription dashboard
    # ==========================

    if data == "subscription":
        try:
            stats = get_subscription_stats()
            users = get_all_users_info(
                limit=30
            )
        except Exception:
            await query.edit_message_text(
                "❌ دریافت اطلاعات اشتراک‌ها ناموفق بود.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        text = (
            "💎 مدیریت اشتراک‌ها\n\n"
            f"👥 کل کاربران: "
            f"{stats['total_users']}\n"
            f"🟢 Free: "
            f"{stats['free']}\n"
            f"⚡ Pro: "
            f"{stats['pro']}\n"
            f"🚀 Ultra: "
            f"{stats['ultra']}\n"
            f"✅ اشتراک فعال: "
            f"{stats['active_subscriptions']}\n\n"
            "کاربر موردنظر را انتخاب کنید:"
        )

        keyboard = []

        for row in users:
            user_id = row[0]
            label = _user_label(
                row
            )

            try:
                sub = get_subscription(
                    user_id
                )
            except Exception:
                sub = {
                    "plan": "free"
                }

            plan = str(
                sub.get(
                    "plan",
                    "free",
                )
            ).upper()

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{label} · {plan}",
                        callback_data=(
                            f"subscription_user:"
                            f"{user_id}"
                        ),
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 بازگشت",
                    callback_data="admin",
                )
            ]
        )

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )

        return True

    # ==========================
    # Single user
    # ==========================

    if data.startswith(
        "subscription_user:"
    ):
        raw_id = data.split(
            ":",
            1,
        )[1].strip()

        try:
            user_id = int(
                raw_id
            )
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه کاربر نامعتبر است.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        try:
            known_users = {
                row[0]
                for row in get_all_users_info(
                    limit=1000
                )
            }
        except Exception:
            await query.edit_message_text(
                "❌ دریافت کاربران ناموفق بود.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        if user_id not in known_users:
            await query.edit_message_text(
                "❌ کاربر پیدا نشد.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        try:
            text = (
                f"👤 کاربر: {user_id}\n\n"
                f"{_subscription_text(user_id)}\n\n"
                "عملیات موردنظر را انتخاب کنید:"
            )
        except Exception:
            await query.edit_message_text(
                "❌ دریافت وضعیت اشتراک کاربر ناموفق بود.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        await query.edit_message_text(
            text,
            reply_markup=(
                _user_subscription_keyboard(
                    user_id
                )
            ),
        )

        return True

    # ==========================
    # Set plan
    # ==========================

    if data.startswith(
        "set_plan:"
    ):
        parts = data.split(
            ":",
            2,
        )

        if len(parts) != 3:
            await query.edit_message_text(
                "❌ درخواست نامعتبر است.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        try:
            user_id = int(
                parts[1]
            )
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه کاربر نامعتبر است.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        plan_name = (
            parts[2]
            .strip()
            .lower()
        )

        if plan_name not in VALID_PLANS:
            await query.edit_message_text(
                "❌ پلن نامعتبر است.",
                reply_markup=(
                    _user_subscription_keyboard(
                        user_id
                    )
                ),
            )
            return True

        try:
            result = activate_user_plan(
                user_id,
                plan_name,
                DEFAULT_DURATION_DAYS,
            )
        except Exception:
            await query.edit_message_text(
                "❌ تغییر پلن ناموفق بود.",
                reply_markup=(
                    _user_subscription_keyboard(
                        user_id
                    )
                ),
            )
            return True

        await query.edit_message_text(
            (
                result
                + "\n\n"
                + _subscription_text(
                    user_id
                )
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 مدیریت کاربر",
                            callback_data=(
                                f"subscription_user:"
                                f"{user_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "👥 لیست اشتراک‌ها",
                            callback_data=(
                                "subscription"
                            ),
                        )
                    ],
                ]
            ),
        )

        return True

    # ==========================
    # Cancel subscription
    # ==========================

    if data.startswith(
        "cancel_subscription:"
    ):
        raw_id = data.split(
            ":",
            1,
        )[1].strip()

        try:
            user_id = int(
                raw_id
            )
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه کاربر نامعتبر است.",
                reply_markup=_back_to_subscriptions(),
            )
            return True

        try:
            result = (
                cancel_user_subscription(
                    user_id
                )
            )
        except Exception:
            await query.edit_message_text(
                "❌ لغو اشتراک ناموفق بود.",
                reply_markup=(
                    _user_subscription_keyboard(
                        user_id
                    )
                ),
            )
            return True

        await query.edit_message_text(
            (
                result
                + "\n\n"
                + _subscription_text(
                    user_id
                )
            ),
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔙 مدیریت کاربر",
                            callback_data=(
                                f"subscription_user:"
                                f"{user_id}"
                            ),
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "👥 لیست اشتراک‌ها",
                            callback_data=(
                                "subscription"
                            ),
                        )
                    ],
                ]
            ),
        )

        return True

    return False