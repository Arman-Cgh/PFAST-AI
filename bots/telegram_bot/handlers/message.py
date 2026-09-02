import logging
import re

from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_ID, is_admin
from database.db import (
    save_message,
    add_user,
    is_user_banned,
    get_admin_action,
    clear_admin_action,
    set_plan_price,
    set_referral_settings,
    set_referral_message_template,
)
from utils.pricing import parse_price_input, format_price
from utils.feature_gate import check_feature_access

# Backward compatibility alias
_parse_price_input = parse_price_input


logger = logging.getLogger(__name__)


def clean_ai_response(text: str) -> str:
    if not text:
        return ""

    return (
        str(text)
        .replace("**", "")
        .replace("__", "")
        .replace("`", "")
        .strip()
    )


def _replace_referral_template_values(
    template: str,
    link: str,
    required_invites: int,
    reward_days: int,
    reward_plan: str,
) -> str:
    return template.format(
        link=link,
        required_invites=required_invites,
        reward_days=reward_days,
        reward_plan=reward_plan,
    )


async def _handle_admin_action(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> bool:

    if not is_admin(update.effective_user.id):
        return False

    user_id = update.effective_user.id
    action = get_admin_action(user_id)

    if not action:
        return False

    # Mandatory-join admin actions are handled before all other admin input.
    from handlers.admin.mandatory_join import handle_mandatory_join_message
    if await handle_mandatory_join_message(update, context):
        return True

    if action == "broadcast":
        from handlers.admin.broadcast import send_broadcast

        return await send_broadcast(
            update,
            context,
        )

    if action.startswith("set_price:"):
        plan_name = action.split(":", 1)[1]

        try:
            amount, currency = parse_price_input(text)

            set_plan_price(
                plan_name,
                amount,
                currency=currency,
            )

            formatted_price = format_price(amount, currency)

            await update.message.reply_text(
                f"✅ قیمت {plan_name.upper()} ذخیره شد: "
                f"{formatted_price}\n"
                "💸 مبلغ جدید در /buy نمایش داده می‌شود."
            )

        except Exception:
            await update.message.reply_text(
                "❌ مبلغ نامعتبر است.\n"
                "مثال: 350000 یا 350/000 تومان 💸"
            )

        clear_admin_action(user_id)
        return True

    # IMPORTANT:
    # This action MUST be handled before the AI path.
    if action == "set_referral_message":
        try:
            set_referral_message_template(text)

            await update.message.reply_text(
                "✅ متن پیام رفرال با موفقیت ذخیره شد."
            )

        except ValueError as exc:
            await update.message.reply_text(
                "❌ متن رفرال نامعتبر است.\n\n"
                "متغیرهای مجاز:\n"
                "{link}\n"
                "{required_invites}\n"
                "{reward_days}\n"
                "{reward_plan}\n\n"
                f"جزئیات: {exc}"
            )

        clear_admin_action(user_id)
        return True

    if action.startswith("set_referral:"):
        field = action.split(":", 1)[1]
        raw = text.strip()

        try:
            if field == "required_invites":
                value = int(raw)
                if value < 1:
                    raise ValueError

                set_referral_settings(
                    required_invites=value
                )

                message = (
                    f"✅ حداقل دعوت روی {value} تنظیم شد."
                )

            elif field == "reward_days":
                value = int(raw)
                if value < 1:
                    raise ValueError

                set_referral_settings(
                    reward_days=value
                )

                message = (
                    f"✅ مدت پاداش روی {value} روز تنظیم شد."
                )

            elif field == "reward_plan":
                value = raw.lower()

                if value not in {
                    "free",
                    "pro",
                    "ultra",
                }:
                    raise ValueError

                set_referral_settings(
                    reward_plan=value
                )

                message = (
                    f"✅ پلن پاداش روی {value.upper()} تنظیم شد."
                )

            else:
                raise ValueError

            await update.message.reply_text(message)

        except ValueError:
            await update.message.reply_text(
                "❌ مقدار نامعتبر است."
            )

        clear_admin_action(user_id)
        return True

    if action in {"image", "technical"}:
        if action == "image":
            access = check_feature_access("image_generation")
            if not access.get("allowed", False):
                clear_admin_action(user_id)
                disabled_msg = (
                    access.get("message")
                    or "⚙️ سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست."
                )
                await update.message.reply_text(disabled_msg)
                return True

        application = getattr(
            context,
            "application",
            None,
        )

        ai_engine = None

        if application:
            ai_engine = (
                application
                .bot_data
                .get("ai_engine")
            )

        if ai_engine is None:
            from services.ai.engine import AIEngine

            ai_engine = AIEngine()

        try:
            result = await ai_engine.generate_response(
                user_id=user_id,
                message=text,
                intent={"intent": "chat"},
            )

            response = clean_ai_response(
                result.get("response", "")
            ) or "پاسخی دریافت نشد."

            await update.message.reply_text(response)

        except Exception:
            logger.exception(
                "Admin action failed: %s",
                action,
            )

            await update.message.reply_text(
                "❌ اجرای عملیات ناموفق بود."
            )

        clear_admin_action(user_id)
        return True

    if action == "ban_user":
        await update.message.reply_text(
            "برای بن، از دکمه «مدیریت بن» و انتخاب کاربر استفاده کنید."
        )

        clear_admin_action(user_id)
        return True

    return False


async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    if not update.message:
        return

    user = update.effective_user

    if not user:
        return

    user_id = user.id

    text = (
        update.message.text
        or ""
    ).strip()

    # Admin actions ALWAYS have priority over AI.
    if is_admin(user_id):
        if await _handle_admin_action(
            update,
            context,
            text,
        ):
            return

    if not text:
        return

    add_user(
        user_id,
        user.username or "",
        user.first_name or "",
    )

    if is_user_banned(user_id):
        await update.message.reply_text(
            "دسترسی شما محدود شده است."
        )
        return


    from handlers.mandatory_join import require_mandatory_join
    if not await require_mandatory_join(update, context):
        return

    # ========================================================
    # 🔒 Privacy Interceptors: Security Tools
    # ========================================================
    user_data = getattr(context, "user_data", None)
    pending_action = user_data.get("pending_action") if isinstance(user_data, dict) else None

    if pending_action == "check_password":
        from handlers.security.password import handle_password_analysis_text
        await handle_password_analysis_text(update, context, text)
        return

    if pending_action == "scan_url":
        from handlers.security.url import handle_url_scan_text
        await handle_url_scan_text(update, context, text)
        return

    if pending_action == "image":
        access = check_feature_access("image_generation")
        if not access.get("allowed", False):
            if isinstance(user_data, dict):
                user_data.pop("pending_action", None)
            disabled_msg = (
                access.get("message")
                or "⚙️ سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست."
            )
            await update.message.reply_text(disabled_msg)
            return

    save_message(
        user_id,
        "user",
        text,
    )

    application = getattr(
        context,
        "application",
        None,
    )

    ai_engine = None

    if application:
        ai_engine = (
            application
            .bot_data
            .get("ai_engine")
        )

    if ai_engine is None:
        from services.ai.engine import AIEngine

        ai_engine = AIEngine()

    try:
        result = await ai_engine.generate_response(
            user_id=user_id,
            message=text,
        )

        response = clean_ai_response(
            result.get("response", "")
        ) or "متاسفانه پاسخی دریافت نشد."

        await update.message.reply_text(response)

        save_message(
            user_id,
            "assistant",
            response,
        )

    except Exception:
        logger.exception(
            "AI response failed"
        )

        await update.message.reply_text(
            "❌ مشکلی در پردازش درخواست پیش آمد."
        )
