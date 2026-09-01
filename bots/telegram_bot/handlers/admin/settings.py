import re

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import (
    clear_admin_action,
    get_admin_action,
    get_plan_prices,
    get_referral_message_template,
    get_referral_settings,
    set_admin_action,
    set_plan_price,
    set_referral_message_template,
    set_referral_settings,
)
from services.billing.plan_service import update_plan
from config import ADMIN_ID, is_admin


def _digits(text):
    return str(text or "").translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))


def _positive_int(text):
    value = _digits(text).strip().replace(",", "").replace("٬", "")
    if not re.fullmatch(r"\d+", value):
        return None
    value = int(value)
    return value if value > 0 else None


def _pricing_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ تغییر Pro", callback_data="set_price:pro"),
            InlineKeyboardButton("🚀 تغییر Ultra", callback_data="set_price:ultra"),
        ],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="admin")],
    ])


def _referral_markup():
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔢 حداقل دعوت", callback_data="referral_edit:required_invites"),
            InlineKeyboardButton("⏳ مدت پاداش", callback_data="referral_edit:reward_days"),
        ],
        [InlineKeyboardButton("💎 پلن پاداش", callback_data="referral_edit:reward_plan")],
        [InlineKeyboardButton("✏️ متن رفرال", callback_data="referral_edit:message")],
        [InlineKeyboardButton("🔙 پنل مدیریت", callback_data="admin")],
    ])


def _plan_back_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 مدیریت پلن‌ها", callback_data="manage_plans")],
    ])


async def handle_settings_callback(update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    user_id = query.from_user.id

    if data == "pricing":
        prices = get_plan_prices()
        lines = ["💰 مدیریت قیمت‌ها", ""]
        for name in ("pro", "ultra"):
            p = prices.get(name, {"price": 0, "currency": "IRR", "duration_days": 30, "is_active": True})
            state = "🟢 فعال" if p.get("is_active", True) else "🔴 غیرفعال"
            lines.append(
                f"• {name.upper()}: {int(p.get('price', 0)):,} {p.get('currency', 'IRR')}"
                f" | {p.get('duration_days', 30)} روز | {state}"
            )
        await query.edit_message_text("\n".join(lines), reply_markup=_pricing_markup())
        return True

    if data.startswith("set_price:"):
        plan_name = data.split(":", 1)[1].strip().lower()
        if plan_name not in {"pro", "ultra"}:
            await query.edit_message_text("❌ پلن نامعتبر است.")
            return True
        set_admin_action(user_id, f"set_price:{plan_name}")
        await query.edit_message_text(
            f"💰 قیمت {plan_name.upper()} را ارسال کنید.\n\n"
            "مثال: 350000 یا 350 هزار تومان"
        )
        return True

    if data == "referral_settings":
        settings = get_referral_settings()
        template = get_referral_message_template()
        await query.edit_message_text(
            "👥 تنظیمات رفرال\n\n"
            f"🔢 حداقل دعوت: {settings['required_invites']}\n"
            f"⏳ مدت پاداش: {settings['reward_days']} روز\n"
            f"💎 پلن پاداش: {settings['reward_plan'].upper()}\n\n"
            f"📝 متن فعلی:\n{template}",
            reply_markup=_referral_markup(),
        )
        return True

    if data == "referral_edit":
        await query.edit_message_text(
            "👥 بخش موردنظر برای تغییر را انتخاب کنید:",
            reply_markup=_referral_markup(),
        )
        return True

    if data.startswith("referral_edit:"):
        field = data.split(":", 1)[1].strip().lower()
        prompts = {
            "required_invites": ("set_referral:required_invites", "🔢 حداقل تعداد دعوت را ارسال کنید. مثال: 3"),
            "reward_days": ("set_referral:reward_days", "⏳ مدت پاداش را بر حسب روز ارسال کنید. مثال: 5"),
            "reward_plan": ("set_referral:reward_plan", "💎 پلن پاداش را ارسال کنید: free / pro / ultra"),
            "message": ("set_referral_message", "✏️ متن جدید رفرال را ارسال کنید.\n\nمتغیرهای مجاز: {link} ، {required_invites} ، {reward_days} ، {reward_plan}"),
        }
        if field not in prompts:
            await query.edit_message_text("❌ گزینه نامعتبر است.")
            return True
        action, prompt = prompts[field]
        set_admin_action(user_id, action)
        await query.edit_message_text(prompt)
        return True

    return False


async def handle_admin_settings_message(update, context):
    user = update.effective_user
    message = update.message
    if not user or not message or not is_admin(user.id):
        return False

    action = get_admin_action(user.id)
    text = (message.text or "").strip()
    if not action or not text:
        return False

    if action.startswith("set_price:"):
        plan_name = action.split(":", 1)[1].lower()
        try:
            amount = set_plan_price(plan_name, text, duration_days=30, currency="IRR")
        except (ValueError, TypeError):
            await message.reply_text("❌ مبلغ نامعتبر است. مثال: 350000 یا 350 هزار تومان")
            return True
        clear_admin_action(user.id)
        await message.reply_text(
            f"✅ قیمت {plan_name.upper()} ذخیره شد: {int(amount):,} IRR",
            reply_markup=_pricing_markup(),
        )
        return True

    if action.startswith("set_referral:"):
        field = action.split(":", 1)[1]
        value = _digits(text).strip()
        try:
            if field == "required_invites":
                number = _positive_int(value)
                if number is None:
                    raise ValueError
                set_referral_settings(required_invites=number)
                reply = f"✅ حداقل دعوت روی {number} تنظیم شد."
            elif field == "reward_days":
                number = _positive_int(value)
                if number is None:
                    raise ValueError
                set_referral_settings(reward_days=number)
                reply = f"✅ مدت پاداش روی {number} روز تنظیم شد."
            elif field == "reward_plan":
                plan = value.lower()
                if plan not in {"free", "pro", "ultra"}:
                    raise ValueError
                set_referral_settings(reward_plan=plan)
                reply = f"✅ پلن پاداش روی {plan.upper()} تنظیم شد."
            else:
                raise ValueError
        except ValueError:
            await message.reply_text("❌ مقدار نامعتبر است.")
            return True
        clear_admin_action(user.id)
        await message.reply_text(reply, reply_markup=_referral_markup())
        return True

    if action == "set_referral_message":
        try:
            set_referral_message_template(text)
        except ValueError as exc:
            await message.reply_text(
                "❌ متن رفرال نامعتبر است.\n\n"
                "متغیرهای مجاز: {link}, {required_invites}, {reward_days}, {reward_plan}\n\n"
                f"جزئیات: {exc}"
            )
            return True
        clear_admin_action(user.id)
        await message.reply_text("✅ متن رفرال ذخیره شد.", reply_markup=_referral_markup())
        return True

    if action.startswith("edit_plan_waiting:"):
        parts = action.split(":", 2)
        if len(parts) != 3:
            clear_admin_action(user.id)
            await message.reply_text("❌ وضعیت ویرایش نامعتبر است.")
            return True
        plan_name, key = parts[1].lower(), parts[2]
        numeric = {"daily_messages", "daily_images", "daily_technical_questions", "cooldown_seconds"}
        value = _digits(text).strip().replace(",", "").replace("٬", "")
        if key in numeric:
            if not re.fullmatch(r"\d+", value):
                await message.reply_text("❌ این فیلد فقط عدد صحیح غیرمنفی می‌پذیرد.")
                return True
            value = int(value)
        ok, detail = update_plan(plan_name, {key: value})
        if not ok:
            await message.reply_text(f"❌ ذخیره نشد: {detail}")
            return True
        clear_admin_action(user.id)
        await message.reply_text("✅ مقدار پلن با موفقیت ذخیره شد.", reply_markup=_plan_back_markup())
        return True

    return False
