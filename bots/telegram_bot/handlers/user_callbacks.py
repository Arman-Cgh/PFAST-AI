from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from config import BOT_NAME

from database.db import (
    get_plan_prices,
    get_referral_link,
    get_referral_settings,
    get_referral_message_template,
    get_user_referral_stats,
    update_payment_gateway,
)

from services.billing.payment_service import (
    create_payment,
    verify_payment,
)

from services.billing.gateway import (
    create_payment_link,
)
from utils.pricing import format_price
from utils.feature_gate import check_feature_access

from handlers.plan import build_plan_text
from handlers.profile import build_profile_text
from handlers.tasks import send_tasks


# ==========================
# Commands
# ==========================

async def buy_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    prices = get_plan_prices()

    text = "💳 پلن‌های قابل خرید:\n\n"

    for plan_name, plan_data in prices.items():
        if plan_name == "free":
            continue

        formatted_p = format_price(
            plan_data["price"],
            plan_data.get("currency", "تومان"),
        )
        text += f"• {plan_name.upper()}: {formatted_p}\n"

    await update.message.reply_text(
        text,
        reply_markup=build_buy_keyboard(prices),
    )


def build_referral_message(
    user_id: int,
    bot_username: str | None,
) -> str:
    referral_link = get_referral_link(
        user_id,
        bot_username,
    )

    if not referral_link:
        return (
            "❌ لینک دعوت شما قابل ساخت نیست.\n\n"
            "نام کاربری ربات در Telegram مشخص نشده است."
        )

    settings = get_referral_settings()
    template = get_referral_message_template()
    stats = get_user_referral_stats(user_id)

    total_invites = int(
        stats.get(
            "invites",
            0,
        )
        or 0
    )

    rewarded = int(
        stats.get(
            "rewarded",
            0,
        )
        or 0
    )

    required_invites = int(
        settings.get(
            "required_invites",
            3,
        )
        or 3
    )

    reward_days = int(
        settings.get(
            "reward_days",
            3,
        )
        or 3
    )

    reward_plan = str(
        settings.get(
            "reward_plan",
            "pro",
        )
        or "pro"
    ).strip().upper()

    remaining_invites = max(
        0,
        required_invites - total_invites,
    )

    try:
        text = template.format(
            link=referral_link,
            required_invites=required_invites,
            reward_days=reward_days,
            reward_plan=reward_plan,
        ).strip()

    except (
        KeyError,
        ValueError,
        AttributeError,
    ):
        text = (
            "👥 لینک دعوت شما:\n"
            f"{referral_link}"
        )

    progress = (
        "\n\n"
        f"👥 دعوت‌های موفق: "
        f"{total_invites} / "
        f"{required_invites}"
    )

    if remaining_invites > 0:
        progress += (
            "\n"
            f"🎁 تا دریافت جایزه "
            f"{remaining_invites} دعوت دیگر مانده."
        )
    else:
        progress += (
            "\n"
            "✅ حد نصاب دعوت تکمیل شده است."
        )

    if rewarded > 0:
        progress += (
            "\n"
            "🏆 پاداش رفرال شما قبلاً فعال شده است."
        )

    return (
        text
        + progress
    )


async def referral_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    bot_username = (
        getattr(
            context.bot,
            "username",
            None,
        )
        or ""
    ).strip().lstrip("@")

    if not bot_username:
        try:
            bot_info = await context.bot.get_me()

            bot_username = (
                getattr(
                    bot_info,
                    "username",
                    None,
                )
                or ""
            ).strip().lstrip("@")

        except Exception:
            bot_username = ""

    await update.message.reply_text(
        build_referral_message(
            user.id,
            bot_username,
        )
    )


# ==========================
# Callback Dispatcher
# ==========================

async def user_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    query = update.callback_query

    if query is None:
        return

    await query.answer()

    data = query.data
    user_id = query.from_user.id

    # ==========================
    # Mandatory join verification
    # ==========================

    if data == "check_mandatory_join":
        from handlers.mandatory_join import (
            check_mandatory_join,
        )

        markup = await check_mandatory_join(
            context.bot,
            user_id,
        )

        if markup is True:
            await query.edit_message_text(
                "✅ عضویت شما تأیید شد. "
                "حالا می‌توانید از ربات استفاده کنید."
            )
        else:
            await query.edit_message_text(
                "🔒 هنوز در همه کانال‌های اجباری عضو نشده‌اید.",
                reply_markup=markup,
            )

        return

    # ==========================
    # Main Menu & Navigation
    # ==========================

    if data == "menu:main":
        context.user_data.pop("pending_action", None)
        await query.edit_message_text(
            "منوی اصلی PFAST_AI:",
            reply_markup=get_main_keyboard(),
        )
        return

    # ==========================
    # Password Security Tools
    # ==========================

    if data.startswith("password:") or data in ("feature:password", "feature:password_tools"):
        from handlers.security.password import handle_password_callback
        if await handle_password_callback(update, context, data):
            return

    # ==========================
    # URL Security Scanner
    # ==========================

    if data.startswith("url:") or data in ("feature:url", "feature:url_scanner"):
        from handlers.security.url import handle_url_callback
        if await handle_url_callback(update, context, data):
            return

    # ==========================
    # Tasks
    # ==========================

    if data == "feature:tasks":
        await send_tasks(
            update,
            context,
        )

        return

    # ==========================
    # Chat
    # ==========================

    if data == "feature:chat":
        context.user_data["pending_action"] = "chat"

        await query.edit_message_text(
            "💬 پیام خود را بفرستید."
        )

        return

    # ==========================
    # Image
    # ==========================

    if data == "feature:image":
        access = check_feature_access("image_generation")
        if not access.get("allowed", False):
            disabled_msg = (
                access.get("message")
                or "⚙️ سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست."
            )
            await query.edit_message_text(disabled_msg)
            return

        context.user_data["pending_action"] = "image"

        await query.edit_message_text(
            "🖼 متن تصویر را ارسال کنید."
        )

        return

    # ==========================
    # Tech
    # ==========================

    if data == "feature:tech":
        context.user_data["pending_action"] = "tech"

        await query.edit_message_text(
            "🧑‍💻 سؤال فنی خود را ارسال کنید."
        )

        return

    # ==========================
    # Profile
    # ==========================

    if data == "feature:profile":
        await query.edit_message_text(
            build_profile_text(user_id)
        )

        return

    # ==========================
    # Plan
    # ==========================

    if data == "feature:plan":
        await query.edit_message_text(
            build_plan_text(user_id)
        )

        return

    # ==========================
    # Buy Menu
    # ==========================

    if data == "feature:buy_subscription":
        prices = get_plan_prices()

        text = "💳 پلن‌های قابل خرید:\n\n"

        for plan_name, plan_data in prices.items():
            if plan_name == "free":
                continue

            formatted_p = format_price(
                plan_data["price"],
                plan_data.get("currency", "تومان"),
            )
            text += f"• {plan_name.upper()}: {formatted_p}\n"

        await query.edit_message_text(
            text,
            reply_markup=build_buy_keyboard(
                prices
            ),
        )

        return

    # ==========================
    # Create Payment
    # ==========================

    if data.startswith("buy:"):
        plan_name = (
            data.split(
                ":",
                1,
            )[1]
            .strip()
            .lower()
        )

        if plan_name not in {
            "pro",
            "ultra",
        }:
            await query.edit_message_text(
                "❌ پلن انتخاب‌ شده معتبر نیست."
            )
            return

        payment = create_payment(
            user_id,
            plan_name,
            30,
        )

        if not payment:
            await query.edit_message_text(
                "❌ ساخت درخواست پرداخت ناموفق بود."
            )

            return

        try:
            gateway = create_payment_link(
                payment["id"],
                payment["amount"],
            )

            update_payment_gateway(
                payment["id"],
                gateway["authority"],
                gateway["url"],
            )

        except Exception:
            await query.edit_message_text(
                "❌ ایجاد لینک پرداخت ناموفق بود."
            )

            return

        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "✅ بررسی پرداخت",
                        callback_data=(
                            f"verify_payment:"
                            f"{payment['id']}:"
                            f"{gateway['authority']}"
                        ),
                    )
                ]
            ]
        )

        payment_url = (
            gateway.get("url")
            or ""
        )

        if payment_url:
            payment_text = (
                f"🔗 لینک پرداخت:\n"
                f"{payment_url}"
            )
        else:
            payment_text = (
                "ℹ️ لینک پرداخت خودکار هنوز "
                "برای این درگاه فعال نشده است.\n"
                "پرداخت باید توسط ادمین بررسی شود."
            )

        await query.edit_message_text(
            (
                f"💳 پرداخت {plan_name.upper()} آماده شد.\n\n"
                f"💰 مبلغ: {payment['amount']} "
                f"{payment['currency']}\n"
                f"📅 مدت: {payment['duration_days']} روز\n\n"
                f"{payment_text}"
            ),
            reply_markup=keyboard,
        )

        return

    # ==========================
    # Verify Payment
    # ==========================

    if data.startswith("verify_payment:"):
        parts = data.split(
            ":",
            2,
        )

        if len(parts) != 3:
            await query.edit_message_text(
                "❌ درخواست بررسی پرداخت نامعتبر است."
            )

            return

        try:
            payment_id = int(
                parts[1]
            )
        except (
            ValueError,
            TypeError,
        ):
            await query.edit_message_text(
                "❌ شناسه پرداخت نامعتبر است."
            )

            return

        authority = parts[2].strip()

        # Security: verify the payment belongs to the requesting user
        from services.billing.payment_service import get_payment
        payment_record = get_payment(payment_id)
        if not payment_record or payment_record.get("user_id") != user_id:
            await query.edit_message_text(
                "❌ دسترسی به این تراکنش مجاز نیست."
            )
            return

        try:
            result = verify_payment(
                payment_id,
                authority,
            )
        except Exception:
            result = False

        if result:
            await query.edit_message_text(
                "✅ پرداخت تأیید شد.\n\n"
                "اشتراک شما فعال شد."
            )
        else:
            await query.edit_message_text(
                "❌ پرداخت هنوز تأیید نشده است.\n\n"
                "در صورت پرداخت موفق، کمی بعد دوباره بررسی کنید."
            )

        return

    # ==========================
    # Referral
    # ==========================

    if data == "feature:referral":
        bot_username = (
            getattr(
                context.bot,
                "username",
                None,
            )
            or ""
        ).strip().lstrip("@")

        if not bot_username:
            try:
                bot_info = await context.bot.get_me()

                bot_username = (
                    getattr(
                        bot_info,
                        "username",
                        None,
                    )
                    or ""
                ).strip().lstrip("@")

            except Exception:
                bot_username = ""

        await query.edit_message_text(
            build_referral_message(
                user_id,
                bot_username,
            )
        )

        return

    # ==========================
    # Help
    # ==========================

    if data == "feature:help":
        await query.edit_message_text(
            (
                f"🆘 راهنمای {BOT_NAME}\n\n"
                "💬 گفت‌وگوی عادی\n"
                "هر چیزی می‌خواهید ارسال کنید.\n\n"
                "🧑‍💻 حالت فنی\n"
                "سؤال برنامه‌نویسی بپرسید.\n\n"
                "🖼 ساخت تصویر\n"
                "متن تصویر را ارسال کنید.\n\n"
                "📋 تسک‌ها\n"
                "برای یادآوری درخواست بدهید."
            )
        )

        return

    await query.edit_message_text(
        "این قابلیت هنوز فعال نشده است."
    )


# ==========================
# Keyboards
# ==========================

def build_buy_keyboard(
    prices,
):
    buttons = []

    for plan_name in (
        "pro",
        "ultra",
    ):
        plan_data = prices.get(
            plan_name,
            {
                "price": 0,
                "currency": "IRR",
            },
        )

        formatted_p = format_price(
            plan_data["price"],
            plan_data.get("currency", "تومان"),
        )
        buttons.append(
            InlineKeyboardButton(
                f"{plan_name.upper()} - {formatted_p}",
                callback_data=f"buy:{plan_name}",
            )
        )

    buttons.append(
        InlineKeyboardButton(
            "🔙 بازگشت",
            callback_data="feature:plan",
        )
    )

    return InlineKeyboardMarkup(
        [
            buttons
        ]
    )


def get_main_keyboard():
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💬 گفت‌وگو",
                    callback_data="feature:chat",
                ),
                InlineKeyboardButton(
                    "🧑‍💻 دستیار فنی",
                    callback_data="feature:tech",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🖼 ساخت تصویر",
                    callback_data="feature:image",
                ),
                InlineKeyboardButton(
                    "📋 تسک‌ها",
                    callback_data="feature:tasks",
                ),
            ],
            [
                InlineKeyboardButton(
                    "👤 پروفایل",
                    callback_data="feature:profile",
                ),
                InlineKeyboardButton(
                    "📊 پلن",
                    callback_data="feature:plan",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🔐 ابزارهای رمز عبور",
                    callback_data="password:menu",
                ),
                InlineKeyboardButton(
                    "🔗 اسکنر پیوندها",
                    callback_data="url:menu",
                ),
            ],
            [
                InlineKeyboardButton(
                    "💳 خرید اشتراک",
                    callback_data="feature:buy_subscription",
                ),
                InlineKeyboardButton(
                    "👥 دعوت",
                    callback_data="feature:referral",
                ),
            ],
            [
                InlineKeyboardButton(
                    "❓ راهنما",
                    callback_data="feature:help",
                )
            ],
        ]
    )

