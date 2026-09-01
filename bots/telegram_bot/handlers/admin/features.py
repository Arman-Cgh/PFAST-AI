from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from services.features.service import list_features_with_status, toggle_feature


def build_features_keyboard() -> InlineKeyboardMarkup:
    features = list_features_with_status()
    keyboard = []

    for feat in features:
        status_emoji = "🟢" if feat["is_enabled"] else "🔴"
        action_text = "غیرفعال‌سازی" if feat["is_enabled"] else "فعال‌سازی"
        btn_text = f"{status_emoji} {feat['display_name']} ({action_text})"
        callback = f"toggle_feature:{feat['name']}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=callback)])

    keyboard.append([InlineKeyboardButton("🔙 پنل مدیریت", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)


def build_features_text() -> str:
    features = list_features_with_status()
    lines = [
        "⚙️ مدیریت قابلیت‌های سیستم (Feature Flags)",
        "",
        "وضعیت فعلی بخش‌های مختلف ربات:",
        "",
    ]
    for feat in features:
        status_text = "🟢 فعال" if feat["is_enabled"] else "🔴 غیرفعال"
        lines.append(f"• {feat['display_name']}: {status_text}")

    lines.append("")
    lines.append("💡 برای تغییر وضعیت هر قابلیت، روی دکمه آن کلیک کنید:")
    return "\n".join(lines)


async def handle_features_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
) -> bool:
    query = update.callback_query
    if not query:
        return False

    if data == "features":
        await query.edit_message_text(
            build_features_text(),
            reply_markup=build_features_keyboard(),
        )
        return True

    if data.startswith("toggle_feature:"):
        feature_name = data.split(":", 1)[1].strip().lower()
        new_status = toggle_feature(feature_name)
        status_str = "🟢 فعال" if new_status else "🔴 غیرفعال"

        await query.answer(f"قابلیت '{feature_name}' اکنون {status_str} شد.")
        await query.edit_message_text(
            build_features_text(),
            reply_markup=build_features_keyboard(),
        )
        return True

    return False

