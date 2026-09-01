from services.billing.plan_service import get_user_limits, get_user_plan
from services.billing.usage_service import check_and_increment_usage


def check_usage_limit(user_id):
    limits = get_user_limits(user_id)

    daily_limit = limits.get(
        "daily_messages",
        0
    )

    return check_and_increment_usage(
        user_id,
        "chat",
        daily_limit
    )