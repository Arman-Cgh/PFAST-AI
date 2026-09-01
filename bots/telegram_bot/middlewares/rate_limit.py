import logging
import time
from typing import Optional

from services.billing.plan_service import get_user_limits

logger = logging.getLogger(__name__)

# Maximum entries to keep in memory before evicting oldest ones.
# Prevents unbounded growth on high-volume bots.
_MAX_CACHE_SIZE = 10_000

# In-memory last-request timestamps: {user_id: float}
user_last_message: dict[int, float] = {}


def _evict_if_needed() -> None:
    """
    Remove the oldest half of the cache when the size limit is reached.
    This is a simple LRU-approximation using sort on insertion time.
    """
    if len(user_last_message) >= _MAX_CACHE_SIZE:
        sorted_ids = sorted(
            user_last_message,
            key=lambda uid: user_last_message[uid],
        )
        to_remove = sorted_ids[: len(sorted_ids) // 2]
        for uid in to_remove:
            user_last_message.pop(uid, None)
        logger.debug(
            "rate_limit: evicted %d stale entries (cache was at capacity)",
            len(to_remove),
        )


def check_rate_limit(user_id: int) -> bool:
    limits = get_user_limits(user_id)

    cooldown = int(
        limits.get("cooldown_seconds", 5) or 5
    )

    now = time.time()
    last_time: Optional[float] = user_last_message.get(user_id)

    logger.debug(
        "rate_limit: user=%s last=%.2f now=%.2f cooldown=%ss",
        user_id,
        last_time or 0.0,
        now,
        cooldown,
    )

    # First message from this user in the current process lifetime
    if last_time is None:
        _evict_if_needed()
        user_last_message[user_id] = now
        logger.debug("rate_limit: user=%s — first message, allowed", user_id)
        return True

    # No cooldown configured for this plan
    if cooldown <= 0:
        user_last_message[user_id] = now
        logger.debug("rate_limit: user=%s — no cooldown, allowed", user_id)
        return True

    diff = now - last_time

    # Still within cooldown window
    if diff < cooldown:
        remaining = cooldown - diff
        logger.debug(
            "rate_limit: user=%s — blocked, wait %.1fs",
            user_id,
            remaining,
        )
        return False

    # Allowed: update timestamp
    user_last_message[user_id] = now
    logger.debug("rate_limit: user=%s — allowed", user_id)
    return True