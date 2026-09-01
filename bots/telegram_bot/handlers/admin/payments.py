from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from database.db import (
    get_all_payment_requests,
    get_payment_request,
)

from services.billing.payment_service import (
    approve_payment,
    reject_payment,
)

from config import ADMIN_ID, is_admin


def _status_text(status: str) -> str:
    return {
        "paid": "✅ تأیید شده",
        "pending": "⏳ در انتظار",
        "failed": "❌ رد شده",
        "cancelled": "🚫 لغو شده",
    }.get(
        str(status or "").strip().lower(),
        "❔ نامشخص",
    )


def _payment_text(payment: dict) -> str:
    payment_id = payment.get("id", "-")
    user_id = payment.get("user_id", "-")
    plan_name = str(
        payment.get("plan_name", "free")
    ).upper()
    amount = int(
        payment.get("amount", 0) or 0
    )
    currency = (
        payment.get("currency")
        or "IRR"
    )
    status = _status_text(
        payment.get("status")
    )
    duration_days = int(
        payment.get("duration_days", 30)
        or 30
    )
    gateway = (
        payment.get("gateway")
        or "placeholder"
    )
    gateway_reference = (
        payment.get("gateway_reference")
        or "-"
    )
    created_at = (
        payment.get("created_at")
        or "-"
    )

    return (
        f"💳 پرداخت #{payment_id}\n\n"
        f"👤 کاربر: {user_id}\n"
        f"📦 پلن: {plan_name}\n"
        f"💰 مبلغ: {amount:,} {currency}\n"
        f"📅 مدت: {duration_days} روز\n"
        f"📌 وضعیت: {status}\n"
        f"🏦 درگاه: {gateway}\n"
        f"🔖 مرجع: {gateway_reference}\n"
        f"🕒 تاریخ: {created_at}"
    )


def _back_to_payments_markup():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🔙 بازگشت به پرداخت‌ها",
                    callback_data="payments",
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


async def handle_payments_callback(
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
    # Payments list
    # ==========================

    if data == "payments":
        try:
            payments = get_all_payment_requests(
                limit=10
            )
        except Exception:
            await query.edit_message_text(
                "❌ دریافت لیست پرداخت‌ها ناموفق بود.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        if not payments:
            await query.edit_message_text(
                "💳 هنوز هیچ پرداختی ثبت نشده است.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        text_lines = [
            "💳 مدیریت پرداخت‌ها",
            "",
        ]

        keyboard = []

        for payment in payments:
            text_lines.extend(
                [
                    f"#{payment.get('id', '-')}",
                    f"👤 User: {payment.get('user_id', '-')}",
                    (
                        "📦 "
                        f"{str(payment.get('plan_name', 'free')).upper()}"
                    ),
                    (
                        "💰 "
                        f"{int(payment.get('amount', 0) or 0):,} "
                        f"{payment.get('currency') or 'IRR'}"
                    ),
                    (
                        "📌 "
                        f"{_status_text(payment.get('status'))}"
                    ),
                    "──────────",
                ]
            )

            payment_id = payment.get("id")
            status = str(
                payment.get("status", "")
            ).strip().lower()

            if payment_id is None:
                continue

            if status == "pending":
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            f"✅ تأیید #{payment_id}",
                            callback_data=(
                                f"approve_payment:{payment_id}"
                            ),
                        ),
                        InlineKeyboardButton(
                            f"❌ رد #{payment_id}",
                            callback_data=(
                                f"reject_payment:{payment_id}"
                            ),
                        ),
                    ]
                )

            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"🔎 جزئیات #{payment_id}",
                        callback_data=(
                            f"payment:{payment_id}"
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
            "\n".join(text_lines),
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )
        return True

    # ==========================
    # Payment details
    # ==========================

    if data.startswith("payment:"):
        raw_id = data.split(
            ":",
            1,
        )[1].strip()

        try:
            payment_id = int(raw_id)
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه پرداخت نامعتبر است.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        try:
            payment = get_payment_request(
                payment_id
            )
        except Exception:
            payment = None

        if not payment:
            await query.edit_message_text(
                "❌ پرداخت موردنظر پیدا نشد.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        keyboard = []

        status = str(
            payment.get("status", "")
        ).strip().lower()

        if status == "pending":
            keyboard.append(
                [
                    InlineKeyboardButton(
                        "✅ تأیید پرداخت",
                        callback_data=(
                            f"approve_payment:{payment_id}"
                        ),
                    ),
                    InlineKeyboardButton(
                        "❌ رد پرداخت",
                        callback_data=(
                            f"reject_payment:{payment_id}"
                        ),
                    ),
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "🔙 پرداخت‌ها",
                    callback_data="payments",
                )
            ]
        )

        await query.edit_message_text(
            _payment_text(payment),
            reply_markup=InlineKeyboardMarkup(
                keyboard
            ),
        )
        return True

    # ==========================
    # Approve payment
    # ==========================

    if data.startswith("approve_payment:"):
        raw_id = data.split(
            ":",
            1,
        )[1].strip()

        try:
            payment_id = int(raw_id)
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه پرداخت نامعتبر است.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        try:
            payment = get_payment_request(
                payment_id
            )
        except Exception:
            payment = None

        if not payment:
            await query.edit_message_text(
                "❌ پرداخت پیدا نشد.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        current_status = str(
            payment.get("status", "")
        ).strip().lower()

        if current_status == "paid":
            await query.edit_message_text(
                "✅ این پرداخت قبلاً تأیید شده است.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        if current_status != "pending":
            await query.edit_message_text(
                (
                    "❌ این پرداخت قابل تأیید نیست.\n\n"
                    f"وضعیت فعلی: "
                    f"{_status_text(current_status)}"
                ),
                reply_markup=_back_to_payments_markup(),
            )
            return True

        try:
            result = approve_payment(
                payment_id
            )
        except Exception:
            result = False

        if result:
            await query.edit_message_text(
                (
                    f"✅ پرداخت #{payment_id} با موفقیت تأیید شد.\n\n"
                    "اشتراک کاربر فعال شد."
                ),
                reply_markup=_back_to_payments_markup(),
            )
        else:
            await query.edit_message_text(
                f"❌ تأیید پرداخت #{payment_id} ناموفق بود.",
                reply_markup=_back_to_payments_markup(),
            )

        return True

    # ==========================
    # Reject payment
    # ==========================

    if data.startswith("reject_payment:"):
        raw_id = data.split(
            ":",
            1,
        )[1].strip()

        try:
            payment_id = int(raw_id)
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه پرداخت نامعتبر است.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        try:
            payment = get_payment_request(
                payment_id
            )
        except Exception:
            payment = None

        if not payment:
            await query.edit_message_text(
                "❌ پرداخت پیدا نشد.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        current_status = str(
            payment.get("status", "")
        ).strip().lower()

        if current_status == "failed":
            await query.edit_message_text(
                "❌ این پرداخت قبلاً رد شده است.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        if current_status == "paid":
            await query.edit_message_text(
                "❌ پرداخت تأییدشده را نمی‌توان رد کرد.",
                reply_markup=_back_to_payments_markup(),
            )
            return True

        if current_status != "pending":
            await query.edit_message_text(
                (
                    "❌ این پرداخت قابل رد کردن نیست.\n\n"
                    f"وضعیت فعلی: "
                    f"{_status_text(current_status)}"
                ),
                reply_markup=_back_to_payments_markup(),
            )
            return True

        try:
            result = reject_payment(
                payment_id
            )
        except Exception:
            result = False

        if result:
            await query.edit_message_text(
                f"✅ پرداخت #{payment_id} رد شد.",
                reply_markup=_back_to_payments_markup(),
            )
        else:
            await query.edit_message_text(
                f"❌ رد پرداخت #{payment_id} ناموفق بود.",
                reply_markup=_back_to_payments_markup(),
            )

        return True

    return False