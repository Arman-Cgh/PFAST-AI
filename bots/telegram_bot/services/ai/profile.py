"""
Profile Engine

این فایل مسئول آماده کردن اطلاعات کاربر
برای Prompt است.
"""

import logging

from database.db import get_profile

logger = logging.getLogger(__name__)


DEFAULT_PROFILE = {
    "username": "",
    "first_name": "",
    "nickname": "",
    "bio": "",
    "interests": ""
}


def load_profile(user_id: int):

    try:
        data = get_profile(user_id)

        if not data:
            return DEFAULT_PROFILE.copy()

        return {
            "username": data[0] or "",
            "first_name": data[1] or "",
            "nickname": data[2] or "",
            "bio": data[3] or "",
            "interests": data[4] or ""
        }

    except Exception:
        logger.warning("Profile load failed for user %s", user_id)
        return DEFAULT_PROFILE.copy()



def profile_to_text(profile: dict):

    text = []

    if profile.get("first_name"):
        text.append(f"نام: {profile['first_name']}")

    if profile.get("nickname"):
        text.append(f"لقب: {profile['nickname']}")

    if profile.get("bio"):
        text.append(f"درباره کاربر: {profile['bio']}")

    if profile.get("interests"):
        text.append(f"علاقه‌ها: {profile['interests']}")

    return "\n".join(text)