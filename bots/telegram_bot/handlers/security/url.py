"""
URL Security Scanner Handler.

Provides the Telegram UI interaction layer for offline URL scanning,
phishing detection, and structural threat assessment.
"""

from typing import Any, Dict, List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from utils.feature_gate import check_feature_access
from services.security.url_scanner import analyze_url_security


INDICATOR_LABELS: Dict[str, str] = {
    "private_or_loopback_ip": "⛔ آدرس شبکه داخلی یا لوپ‌بک (ریسک SSRF)",
    "raw_ip_host": "⚠️ استفاده از IP مستقیم به جای نام دامنه",
    "punycode_or_homograph": "⚠️ دامنه حاوی حروف یونیکد یا پونی‌کد (ریسک جعل برند)",
    "embedded_credentials": "⚠️ نام کاربری یا رمز عبور تعبیه‌شده در لینک",
    "url_shortener": "⚠️ لینک کوتاه‌شده (مقصد نهایی پنهان است)",
    "excessive_subdomains": "⚠️ زیردامنه‌های تودرتوی متعدد و مشکوک",
    "suspicious_redirect_params": "⚠️ پارامترهای هدایت‌کننده (Open Redirect)",
    "insecure_http": "ℹ️ ارتباط رمزنگاری‌نشده (HTTP)",
    "excessive_length": "ℹ️ طول آدرس بیش از حد معمول",
    "unsafe_scheme": "⛔ پروتکل مسدود یا ناامن",
    "malformed_port": "⚠️ درگاه نامعتبر در ساختار آدرس",
}


def get_url_menu_text() -> str:
    return (
        "🔗 **مرکز اسکن و امنیت پیوندها (URL)**\n\n"
        "این ابزار به صورت محلی و هوشمند ساختار لینک‌ها را جهت شناسایی فیشینگ، "
        "بدافزارها، دامنه‌های جعلی (Homograph) و رفتارهای مشکوک بررسی می‌کند.\n\n"
        "🛡 **ویژگی‌های کلیدی:**\n"
        "• تحلیل ۱۰۰٪ محلی، آفلاین و سریع بدون اتصال سرور به لینک\n"
        "• شناسایی پسوندهای خطرناک، لینک‌های کوتاه‌شده و پونی‌کد\n"
        "• حفظ کامل حریم خصوصی و امنیت کاربر"
    )


def get_url_menu_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "🔍 اسکن و بررسی لینک جدید",
                callback_data="url:scan_prompt",
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


def get_scan_prompt_text() -> str:
    return (
        "🔍 **اسکن و بررسی پیوند اینترنتی**\n\n"
        "لطفاً لینک یا آدرس وب‌سایت مورد نظر خود را در قالب پیام ارسال کنید:\n"
        "`https://example.com/page`\n\n"
        "🛡 **تضمین حریم خصوصی و امنیت:**\n"
        "• سرور ربات مستقیماً به این آدرس متصل نمی‌شود.\n"
        "• لینک ارسالی در دیتابیس ذخیره نشده و به هوش مصنوعی ارسال نمی‌گردد."
    )


def get_scan_prompt_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton(
                "🔙 انصراف و بازگشت",
                callback_data="url:menu",
            ),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def format_url_report(analysis: Dict[str, Any]) -> str:
    if not analysis.get("valid", False) and analysis.get("risk_level") == "invalid":
        return (
            "⚠️ **خطا در پردازش لینک**\n\n"
            "ساختار آدرس ارسال شده نامعتبر است. لطفاً یک آدرس وب استاندارد (شامل دامنه) ارسال کنید."
        )

    risk_map = {
        "safe": "🟢 امن و بدون ریسک شناسایی‌شده",
        "suspicious": "🟡 مشکوک و نیازمند احتیاط",
        "dangerous": "🔴 خطرناک و با ریسک بالا",
    }

    risk_level = analysis.get("risk_level", "suspicious")
    risk_title = risk_map.get(risk_level, "🟡 نامشخص")
    score = analysis.get("score", 0)
    hostname = analysis.get("hostname", "-")
    scheme = (analysis.get("scheme") or "-").upper()
    normalized_url = analysis.get("normalized_url", "")

    # Progress bar for risk score
    filled = score // 10
    empty = 10 - filled
    progress_bar = ("🟥" * filled) + ("⬜️" * empty) if score >= 60 else ("🟨" * filled) + ("⬜️" * empty) if score >= 25 else ("🟩" * filled) + ("⬜️" * empty)

    lines = [
        "🛡 **گزارش ارزیابی امنیت پیوند**",
        "━━━━━━━━━━━━━━━━━━━━",
        f"📊 **سطح ریسک:** {risk_title}",
        f"امتیاز خطر: **{score} / 100**",
        f"[{progress_bar}]",
        "",
        f"• **دامنه / میزبان:** `{hostname}`",
        f"• **پروتکل:** `{scheme}`",
    ]

    if normalized_url:
        lines.append(f"• **آدرس نرمال‌شده:** `{normalized_url}`")

    indicators = analysis.get("indicators", [])
    if indicators:
        lines.extend(["", "⚠️ **شاخص‌های مشکوک شناسایی‌شده:**"])
        for ind in indicators:
            if ind in INDICATOR_LABELS:
                lines.append(f"• {INDICATOR_LABELS[ind]}")
            elif ind.startswith("dangerous_extension_"):
                ext = ind.replace("dangerous_extension_", ".")
                lines.append(f"• ⛔ فایل اجرایی یا اسکریپت ({ext})")
            elif ind.startswith("non_standard_port_"):
                port_num = ind.replace("non_standard_port_", "")
                lines.append(f"• ⚠️ استفاده از درگاه غیرمعمول ({port_num})")
            elif ind.startswith("suspicious_tld_"):
                tld_name = ind.replace("suspicious_tld_", ".")
                lines.append(f"• ⚠️ پسوند دامنه پرخطر ({tld_name})")
            elif ind.startswith("brand_spoof_"):
                brand = ind.replace("brand_spoof_", "")
                lines.append(f"• ⚠️ احتمال جعل برند ({brand})")
            elif ind.startswith("phishing_action_"):
                act = ind.replace("phishing_action_", "")
                lines.append(f"• ⚠️ واژه حساس فیشینگ ({act})")
            else:
                lines.append(f"• {ind}")

    recommendations = analysis.get("recommendations", [])
    if recommendations:
        lines.extend(["", "💡 **توصیه‌های امنیتی:**"])
        for rec in recommendations:
            lines.append(f"• {rec}")

    lines.extend([
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "🔒 *بررسی به صورت ۱۰۰٪ محلی انجام شده و سرور مستقیماً به لینک متصل نشده است.*",
    ])
    return "\n".join(lines)


def get_url_result_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [
            InlineKeyboardButton("🔍 اسکن یک لینک دیگر", callback_data="url:scan_prompt"),
        ],
        [
            InlineKeyboardButton("🔙 بازگشت به مرکز اسکنر", callback_data="url:menu"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


async def handle_url_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    data: str,
) -> bool:
    """
    Dispatcher for URL scanner inline button callbacks.
    """
    query = update.callback_query
    if not query:
        return False

    # 1. Feature Gate check
    access = check_feature_access("url_scanner")
    if not access.get("allowed", False):
        disabled_msg = access.get("message") or "⚙️ ابزار اسکنر پیوند موقتاً غیرفعال است."
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="menu:main")]
        ])
        await query.edit_message_text(disabled_msg, reply_markup=keyboard)
        return True

    # 2. Main Menu
    if data in ("url:menu", "feature:url_scanner", "feature:url"):
        context.user_data.pop("pending_action", None)
        await query.edit_message_text(
            get_url_menu_text(),
            reply_markup=get_url_menu_keyboard(),
            parse_mode="Markdown",
        )
        return True

    # 3. Scan Prompt (Initiate scan flow)
    if data == "url:scan_prompt":
        context.user_data["pending_action"] = "scan_url"
        await query.edit_message_text(
            get_scan_prompt_text(),
            reply_markup=get_scan_prompt_keyboard(),
            parse_mode="Markdown",
        )
        return True

    return False


async def handle_url_scan_text(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    text: str,
) -> bool:
    """
    Analyzes submitted URL text locally and renders the security report card.
    """
    context.user_data.pop("pending_action", None)

    analysis = analyze_url_security(text)
    report_text = format_url_report(analysis)

    await update.message.reply_text(
        report_text,
        reply_markup=get_url_result_keyboard(),
        parse_mode="Markdown",
    )
    return True

