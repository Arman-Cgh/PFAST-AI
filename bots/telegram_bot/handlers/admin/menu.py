from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def get_admin_menu():
    keyboard = [
        [
            InlineKeyboardButton("👥 کاربران", callback_data="users"),
            InlineKeyboardButton("📊 آمار", callback_data="stats"),
        ],
        [
            InlineKeyboardButton("💳 پرداخت‌ها", callback_data="payments"),
            InlineKeyboardButton("💎 اشتراک‌ها", callback_data="subscription"),
        ],
        [
            InlineKeyboardButton("⚙️ مدیریت پلن‌ها", callback_data="manage_plans"),
            InlineKeyboardButton("💰 قیمت‌ها", callback_data="pricing"),
        ],
        [
            InlineKeyboardButton("👥 رفرال", callback_data="referral_settings"),
            InlineKeyboardButton("🔒 جوین اجباری", callback_data="mandatory_join"),
        ],
        [
            InlineKeyboardButton("📢 ارسال همگانی", callback_data="broadcast"),
            InlineKeyboardButton("🚫 مدیریت بن", callback_data="ban_user"),
        ],
        [
            InlineKeyboardButton("⚙️ قابلیت‌ها (Flags)", callback_data="features"),
            InlineKeyboardButton("🖼 تصویر", callback_data="image"),
        ],
        [
            InlineKeyboardButton("🧠 سوال فنی", callback_data="technical"),
            InlineKeyboardButton("❌ بستن", callback_data="close"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
