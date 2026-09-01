import logging

from services.billing.plan_service import (
    get_user_limits,
    get_user_plan,
)

from services.billing.usage_service import (
    get_usage,
    add_usage,
    check_and_increment_usage,
)


logger = logging.getLogger(__name__)


FEATURE_CONFIG = {
    "chat": {
        "limit_key": "daily_messages",
        "usage_key": "messages",
    },
    "image": {
        "limit_key": "daily_images",
        "usage_key": "images",
    },
    "technical": {
        "limit_key": "daily_technical_questions",
        "usage_key": "code_requests",
    },
    "vision": {
        "limit_key": "daily_images",
        "usage_key": "searches",
    },
}


def _get_feature_config(
    feature_name,
):
    feature = (
        str(feature_name or "")
        .strip()
        .lower()
    )

    return (
        feature,
        FEATURE_CONFIG.get(feature),
    )


def _get_user_limits(
    user_id,
):
    limits = get_user_limits(
        user_id
    )

    if not isinstance(
        limits,
        dict,
    ):
        raise ValueError(
            "Invalid user limits payload"
        )

    return limits


def _get_feature_limit(
    user_id,
    feature_name,
):
    feature, config = _get_feature_config(
        feature_name
    )

    if config is None:
        logger.warning(
            "Unknown feature '%s' for user %s",
            feature_name,
            user_id,
        )
        return None

    limits = _get_user_limits(
        user_id
    )

    limit_key = config[
        "limit_key"
    ]

    if limit_key not in limits:
        logger.error(
            "Missing plan limit '%s' for user %s. "
            "Available keys: %s",
            limit_key,
            user_id,
            list(limits.keys()),
        )
        return None

    value = limits.get(
        limit_key
    )

    if value is None:
        logger.error(
            "Plan limit '%s' is None for user %s",
            limit_key,
            user_id,
        )
        return None

    try:
        value = int(value)

    except (
        TypeError,
        ValueError,
    ):
        logger.error(
            "Invalid plan limit '%s'=%r for user %s",
            limit_key,
            value,
            user_id,
        )
        return None

    if value < 0:
        logger.error(
            "Negative plan limit '%s'=%s for user %s",
            limit_key,
            value,
            user_id,
        )
        return None

    return value


def _get_cooldown_seconds(
    user_id,
):
    limits = _get_user_limits(
        user_id
    )

    value = limits.get(
        "cooldown_seconds",
        0,
    )

    try:
        value = float(
            value or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        logger.error(
            "Invalid cooldown_seconds=%r for user %s",
            value,
            user_id,
        )
        return 0.0

    return max(
        0.0,
        value,
    )


def can_use_feature(
    user_id,
    feature_name,
):
    """
    Read-only daily-limit check.

    Cooldown is intentionally not consumed here.
    Runtime request enforcement belongs to
    check_and_consume_feature().
    """

    feature, config = _get_feature_config(
        feature_name
    )

    if config is None:
        return False

    limit = _get_feature_limit(
        user_id,
        feature,
    )

    if limit is None:
        return False

    try:
        usage = get_usage(
            user_id
        )

    except Exception:
        logger.exception(
            "Failed to load usage for user %s",
            user_id,
        )
        return False

    usage_key = config[
        "usage_key"
    ]

    try:
        used = int(
            usage.get(
                usage_key,
                0,
            )
            or 0
        )

    except (
        TypeError,
        ValueError,
    ):
        logger.error(
            "Invalid usage '%s' for user %s",
            usage_key,
            user_id,
        )
        return False

    if used < 0:
        return False

    return used < limit


def increment_feature_usage(
    user_id,
    feature_name,
    amount=1,
):
    """
    Raw usage increment kept for backward compatibility.
    Strict enforcement should use check_and_consume_feature().
    """

    feature, config = _get_feature_config(
        feature_name
    )

    if config is None:
        logger.warning(
            "Unknown feature '%s' for user %s",
            feature_name,
            user_id,
        )
        return False

    try:
        amount = int(
            amount
        )

    except (
        TypeError,
        ValueError,
    ):
        return False

    if amount <= 0:
        return False

    try:
        return bool(
            add_usage(
                user_id,
                feature,
                amount,
            )
        )

    except Exception:
        logger.exception(
            "Failed to increment usage "
            "for feature '%s', user %s",
            feature,
            user_id,
        )
        return False


def check_and_consume_feature(
    user_id,
    feature_name,
    amount=1,
):
    """
    Central permission gate for the active request path.

    Enforces:
        1. known feature
        2. daily plan limit
        3. cooldown
        4. atomic usage consumption
    """

    feature, config = _get_feature_config(
        feature_name
    )

    if config is None:
        logger.warning(
            "Unknown feature '%s' for user %s",
            feature_name,
            user_id,
        )
        return False

    try:
        amount = int(
            amount
        )

    except (
        TypeError,
        ValueError,
    ):
        logger.warning(
            "Invalid usage amount for "
            "feature '%s', user %s: %r",
            feature,
            user_id,
            amount,
        )
        return False

    if amount <= 0:
        logger.warning(
            "Usage amount must be positive. "
            "feature=%s user=%s amount=%s",
            feature,
            user_id,
            amount,
        )
        return False

    limit = _get_feature_limit(
        user_id,
        feature,
    )

    if limit is None:
        return False

    if amount > limit:
        return False

    cooldown_seconds = _get_cooldown_seconds(
        user_id
    )

    try:
        return bool(
            check_and_increment_usage(
                user_id=user_id,
                feature=feature,
                limit=limit,
                amount=amount,
                cooldown_seconds=cooldown_seconds,
            )
        )

    except TypeError:
        # Backward compatibility with an older usage
        # implementation that does not yet accept
        # cooldown_seconds.
        try:
            return bool(
                check_and_increment_usage(
                    user_id,
                    feature,
                    limit,
                    amount,
                )
            )

        except Exception:
            logger.exception(
                "Usage enforcement failed "
                "for feature '%s', user %s",
                feature,
                user_id,
            )
            return False

    except Exception:
        logger.exception(
            "Usage enforcement failed "
            "for feature '%s', user %s",
            feature,
            user_id,
        )
        return False


def get_current_user_plan(
    user_id,
):
    return get_user_plan(
        user_id
    )