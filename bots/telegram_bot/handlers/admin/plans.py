from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from database.db import set_admin_action
from services.billing.plan_service import get_all_plans, get_plan


EDITABLE_FIELDS = {
    "daily_messages",
    "daily_images",
    "daily_technical_questions",
    "cooldown_seconds",
}


async def handle_plans_callback(update, context: ContextTypes.DEFAULT_TYPE, data: str):
    query = update.callback_query
    user_id = query.from_user.id

    if data == "manage_plans":
        plans = get_all_plans()
        text = "⚙️ مدیریت پلن‌ها\n\n"
        for name in ("free", "pro", "ultra"):
            plan = plans.get(name)
            text += f"• {name.upper()}: {'✅ موجود' if plan else '❌ پیدا نشد'}\n"

        keyboard = [[
            InlineKeyboardButton("Free", callback_data="manage_plans:free"),
            InlineKeyboardButton("Pro", callback_data="manage_plans:pro"),
            InlineKeyboardButton("Ultra", callback_data="manage_plans:ultra"),
        ], [InlineKeyboardButton("🔙 بازگشت", callback_data="admin")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if data.startswith("manage_plans:"):
        plan_name = data.split(":", 1)[1].strip().lower()
        plan = get_plan(plan_name)
        if not plan:
            await query.edit_message_text("❌ پلن موردنظر پیدا نشد.")
            return True

        text = f"⚙️ تنظیمات پلن {plan_name.upper()}\n\n"
        keyboard = []
        row = []
        for key, value in plan.items():
            if key in {"id", "name"}:
                continue
            text += f"• {key}: {value if value is not None else '(خالی)'}\n"
            if key in EDITABLE_FIELDS:
                row.append(InlineKeyboardButton("✏️ " + key, callback_data=f"edit_plan:{plan_name}:{key}"))
                if len(row) == 2:
                    keyboard.append(row)
                    row = []
        if row:
            keyboard.append(row)
        keyboard.append([InlineKeyboardButton("🔙 پلن‌ها", callback_data="manage_plans")])
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return True

    if data.startswith("edit_plan:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            await query.edit_message_text("❌ درخواست نامعتبر است.")
            return True
        plan_name, key = parts[1].lower(), parts[2]
        if plan_name not in {"free", "pro", "ultra"} or key not in EDITABLE_FIELDS:
            await query.edit_message_text("❌ فیلد قابل ویرایش نیست.")
            return True
        if not get_plan(plan_name):
            await query.edit_message_text("❌ پلن پیدا نشد.")
            return True
        set_admin_action(user_id, f"edit_plan_waiting:{plan_name}:{key}")
        await query.edit_message_text(
            f"✏️ مقدار جدید {key} برای پلن {plan_name.upper()} را ارسال کنید.\n\n"
            "برای فیلدهای عددی فقط عدد صحیح غیرمنفی ارسال کنید."
        )
        return True

    return False
