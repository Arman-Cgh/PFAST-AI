"""
Central Feature Registry for PFAST_AI.

This module is the single source of truth for all feature definitions,
their default states, categories, human-readable display names, and
user-facing disabled/maintenance messages.
"""

from typing import Any, Dict, Optional


FEATURE_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "task": {
        "name": "task",
        "category": "productivity",
        "display_name": "📋 مدیریت تسک‌ها و یادآورها",
        "default_enabled": True,
        "disabled_message": "⚙️ سیستم مدیریت کارها و یادآورها موقتاً در حال بروزرسانی است.",
    },
    "memory": {
        "name": "memory",
        "category": "ai",
        "display_name": "🧠 حافظه بلندمدت و پروفایل",
        "default_enabled": True,
        "disabled_message": "⚙️ سیستم استخراج و بازیابی حافظه هوشمند موقتاً غیرفعال است.",
    },
    "image_generation": {
        "name": "image_generation",
        "category": "ai",
        "display_name": "🖼 ساخت و تولید تصویر",
        "default_enabled": True,
        "disabled_message": "⚙️ سرویس تولید تصویر هوش مصنوعی موقتاً در دسترس نیست.",
    },
    "security_tools": {
        "name": "security_tools",
        "category": "security",
        "display_name": "🛡 مرکز ابزارهای امنیت سایبری",
        "default_enabled": True,
        "disabled_message": "⚙️ مجموعه ابزارهای امنیت سایبری موقتاً در دست تعمیر است.",
    },
    "password_tools": {
        "name": "password_tools",
        "category": "security",
        "display_name": "🔐 ابزارهای رمز عبور (ساخت و ارزیابی)",
        "default_enabled": True,
        "disabled_message": "⚙️ ابزارهای تولید و ارزیابی رمز عبور موقتاً غیرفعال هستند.",
    },
    "url_scanner": {
        "name": "url_scanner",
        "category": "security",
        "display_name": "🔗 اسکنر پیوند و لینک‌های مشکوک",
        "default_enabled": True,
        "disabled_message": "⚙️ سرویس اسکن لینک و فیشینگ موقتاً در حال ارتقا است.",
    },
    "admin_tools": {
        "name": "admin_tools",
        "category": "admin",
        "display_name": "🛠 ابزارهای مدیریت و نظارت",
        "default_enabled": True,
        "disabled_message": "⚙️ پنل مدیریتی موقتاً در دسترس نیست.",
    },
}


def get_feature_definition(feature_name: str) -> Optional[Dict[str, Any]]:
    """
    Get the immutable metadata definition of a feature by its key.
    Returns a copy of the dictionary or None if the feature is unknown.
    """
    feature_name = str(feature_name or "").strip().lower()
    if not feature_name or feature_name not in FEATURE_DEFINITIONS:
        return None
    return dict(FEATURE_DEFINITIONS[feature_name])


def get_all_features() -> Dict[str, Dict[str, Any]]:
    """
    Get all registered features and their metadata definitions.
    """
    return {name: dict(defn) for name, defn in FEATURE_DEFINITIONS.items()}


def validate_feature_exists(feature_name: str) -> bool:
    """
    Check whether a feature is registered in the central registry.
    """
    feature_name = str(feature_name or "").strip().lower()
    return bool(feature_name and feature_name in FEATURE_DEFINITIONS)

