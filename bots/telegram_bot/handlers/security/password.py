"""
Password Security Tools Handler.

Provides the Telegram UI interaction layer for secure password generation
and local, privacy-guaranteed password strength analysis.
"""

from typing import Dict, Any
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils.feature_gate import check_feature_access
from services.security.password import (
    generate_secure_password,
    analyze_password_strength,
)


DEFAULT_GEN_OPTS: Dict[str, Any] = {
    "length": 16,
    "upper": True,
    "lower": True,
    "digits": True,
    "symbols": True,
}


def _get_user_gen_opts(context: ContextTypes.DEFAULT_TYPE) -> Dict[str, Any]:
    """Retrieve or initialize generator settings from user_data."""
    if "pwd_gen_opts" not in context.user_data:
        context.user_data["pwd_gen_opts"] = dict(DEFAULT_GEN_OPTS)
    return context.user_data["pwd_gen_opts"]


def get_password_menu_text() -> str:
    return (
        "🔐 **مرکز ابزارهای رمز عبور امن**\n\n"
        "یکی از ابزارهای زیر را برای شروع انتخاب کنید:\n\n"
        "• **🔑 ساخت رمز عبور امن:** تولید گذرواژه‌های غیرقابل نفوذ بر پایه تصادف رمزنprofileگاری شده.\n"
        "• **🔍 بررسی قدرت رمز:** تحلیل محلی و آفلاین انتروپی، طول، تنوع و الگوهای آسیب‌پذیر بدون ذخیره‌سازی."
    )


def get_password_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "🔑 ساخت رمز عبور امن",
                callback_data="password:gen_menu",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔍 بررسی قدرت رمز عبور",
                callback_data="password:check_menu",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔙 بازگشت به منوی اصلی",
                callback_data="menu:main",
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def get_generator_text(generated_password: str = None) -> str:
    lines = [
        "🔑 **تولیدکننده رمز عبور امن**",
        "",
        "تنظیمات طول و کاراکترهای مورد نظر خود را مشخص کنید و روی دکمه «تولید رمز» بزنید:",
        "",
    ]
    if generated_password:
        lines.extend([
            "━━━━━━━━━━━━━━━━━━━━",
            "🔐 **رمز عبور تولید شده:**",
            f"`{generated_password}`",
            "*(برای کپی، روی رمز ضربه بزنید)*",
            "━━━━━━━━━━━━━━━━━━━━",
            "",
        ])
    return "\n".join(lines)


def get_generator_keyboard(opts: Dict[str, Any]) -> InlineKeyboardMarkup:
    curr_len = opts.get("length", 16)
    len_12_label = "✅ 12" if curr_len == 12 else "12"
    len_16_label = "✅ 16" if curr_len == 16 else "16"
    len_24_label = "✅ 24" if curr_len == 24 else "24"

    upper_label = "🔠 بزرگ: 🟢" if opts.get("upper", True) else "🔠 بزرگ: 🔴"
    lower_label = "🔡 کوچک: 🟢" if opts.get("lower", True) else "🔡 کوچک: 🔴"
    digits_label = "🔢 اعداد: 🟢" if opts.get("digits", True) else "🔢 اعداد: 🔴"
    symbols_label = "🔣 نمادها: 🟢" if opts.get("symbols", True) else "🔣 نمادها: 🔴"

    keyboard = [
        [
            InlineKeyboardButton(f"طول: {len_12_label}", callback_data="password:set_len:12"),
            InlineKeyboardButton(f"طول: {len_16_label}", callback_data="password:set_len:16"),
            InlineKeyboardButton(f"طول: {len_24_label}", callback_data="password:set_len:24"),
        ],
        [
            InlineKeyboardButton(upper_label, callback_data="password:toggle:upper"),
            InlineKeyboardButton(lower_label, callback_data="password:toggle:lower"),
        ],
        [
            InlineKeyboardButton(digits_label, callback_data="password:toggle:digits"),
            InlineKeyboardButton(symbols_label, callback_data="password:toggle:symbols"),
        ],
        [
            InlineKeyboardButton("🎲 تولید رمز جدید", callback_data="password:gen"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به ابزارهای رمز", callback_data="password:menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def format_strength_report(analysis: Dict[str, Any]) -> str:
    strength_map = {
        "very_weak": "🔴 بسیار ضعیف و آسیب‌پذیر",
        "weak": "🟠 ضعیف",
        "medium": "🟡 متوسط و قابل قبول",
        "strong": "🟢 قوی و امن",
        "very_strong": "💎 فوق‌العاده مستحکم و ایمن",
    }

    strength_title = strength_map.get(analysis.get("strength"), "نامشخص")
    score = analysis.get("score", 0)
    entropy = analysis.get("estimated_entropy", 0.0)
    length = analysis.get("length", 0)

    # Visual score progress bar
    filled = score // 10
    empty = 10 - filled
    progress_bar = ("🟩" * filled) + ("⬜️" * empty)

    lines = [
        "🛡 **گزارش ارزیابی قدرت رمز عبور**",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 **سطح امنیت:** {strength_title}",
        f"امتیاز: **{score} / 100**",
        f"[{progress_bar}]",
        "",
        f"• **طول کاراکترها:** {length}",
        f"• **تخمین انتروپی:** {entropy} بیت",
        "",
        "💡 **توصیه‌ها و نکات امنیتی:**",
    ]

    feedback = analysis.get("feedback", [])
    if feedback:
        for item in feedback:
            lines.append(f"• {item}")
    else:
        lines.append("• ساختار و تنوع کاراکترهای رمز عبور بسیار مناسب است.")

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🔒 *توجه: این بررسی ۱۰۰٪ محلی بوده و رمز شما ذخیره نشده است.*",
    ])
    return "\n".join(lines)


def get_analysis_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🔍 بررسی یک رمز دیگر", callback_data="password:check_menu"),
            InlineKeyboardButton("🔑 ساخت رمز امن", callback_data="password:gen_menu"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به ابزارهای رمز", callback_data="password:menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_password_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
) -> bool:
    """
    Dispatcher for all password-related inline button callbacks.
    """
    query = update.callback_query
    if not query:
        return False

    # 1. Feature Gate check
    access = check_feature_access("password_tools")
    if not access.get("allowed", False):
        disabled_msg = access.get("message") or "⚙️ ابزارهای رمز عبور موقتاً غیرفعال هستند."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="menu:main")]
        ])
        await query.edit_message_text(disabled_msg, reply_markup=keyboard)
        return True

    # 2. Main Menu
    if data in ("password:menu", "feature:password", "feature:password_tools"):
        context.user_data.pop("pending_action", None)
        await query.edit_message_text(
            get_password_menu_text(),
            reply_markup=get_password_menu_keyboard(),
            parse_mode="Markdown",
        )
        return True

    # 3. Generator Menu
    if data == "password:gen_menu":
        opts = _get_user_gen_opts(context)
        await query.edit_message_text(
            get_generator_text(),
            reply_markup=get_generator_keyboard(opts),
            parse_mode="Markdown",
        )
        return True

    # 4. Generate Password
    if data == "password:gen":
        opts = _get_user_gen_opts(context)
        try:
            generated = generate_secure_password(
                length=opts.get("length", 16),
                include_uppercase=opts.get("upper", True),
                include_lowercase=opts.get("lower", True),
                include_digits=opts.get("digits", True),
                include_symbols=opts.get("symbols", True),
            )
        except ValueError as e:
            # Fallback if user disabled all options
            opts["upper"] = True
            opts["lower"] = True
            opts["digits"] = True
            opts["symbols"] = True
            generated = generate_secure_password(length=16)

        await query.edit_message_text(
            get_generator_text(generated_password=generated),
            reply_markup=get_generator_keyboard(opts),
            parse_mode="Markdown",
        )
        return True

    # 5. Configure Generator: Length
    if data.startswith("password:set_len:"):
        length_val = int(data.split(":", 2)[2])
        opts = _get_user_gen_opts(context)
        opts["length"] = length_val
        await query.edit_message_text(
            get_generator_text(),
            reply_markup=get_generator_keyboard(opts),
            parse_mode="Markdown",
        )
        return True

    # 6. Configure Generator: Toggle Groups
    if data.startswith("password:toggle:"):
        group = data.split(":", 2)[2]
        opts = _get_user_gen_opts(context)
        if group in opts:
            # Ensure at least one group remains enabled
            current_val = opts[group]
            active_count = sum(1 for k in ("upper", "lower", "digits", "symbols") if opts.get(k, False))
            if current_val and active_count <= 1:
                await query.answer("حداقل باید یک نوع کاراکتر فعال باشد.", show_alert=True)
                return True
            opts[group] = not current_val

        await query.edit_message_text(
            get_generator_text(),
            reply_markup=get_generator_keyboard(opts),
            parse_mode="Markdown",
        )
        return True

    # 7. Check Strength Menu
    if data == "password:check_menu":
        context.user_data["pending_action"] = "check_password"
        prompt_text = (
            "🔍 **تست و ارزیابی قدرت رمز عبور**\n\n"
            "لطفاً رمز عبور مورد نظر خود را در قالب پیام ارسال کنید:\n\n"
            "🛡 **تضمین حریم خصوصی و امنیت:**\n"
            "• بررسی به صورت کاملاً آفلاین و محلی انجام می‌شود.\n"
            "• رمز شما در هیچ پایگاه‌داده‌ای ذخیره نمی‌شود و لاگ نمی‌گردد.\n"
            "• رمز عبور به هیچ مدل هوش مصنوعی یا سروری ارسال نمی‌شود."
        )
        back_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 انصراف و بازگشت", callback_data="password:menu")]
        ])
        await query.edit_message_text(prompt_text, reply_markup=back_kb, parse_mode="Markdown")
        return True

    return False


async def handle_password_analysis_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> bool:
    """
    Directly analyzes password text when user is in the 'check_password' state.
    """
    context.user_data.pop("pending_action", None)

    # Local, deterministic analysis
    analysis = analyze_password_strength(text)
    report_text = format_strength_report(analysis)

    await update.message.reply_text(
        report_text,
        reply_markup=get_analysis_keyboard(),
        parse_mode="Markdown",
    )
    return True

