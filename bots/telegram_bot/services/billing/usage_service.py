from datetime import datetime
from typing import Dict

from database.db import get_connection


FEATURE_COLUMN_MAP = {
    "chat": "messages",
    "image": "images",
    "technical": "code_requests",
    "vision": "searches",
}


USAGE_COLUMNS = {
    "messages": 0,
    "images": 1,
    "code_requests": 2,
    "searches": 3,
}


def get_today():
    return datetime.now().date().isoformat()


def get_usage(
    user_id,
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                messages,
                images,
                code_requests,
                searches
            FROM usage
            WHERE user_id=?
            AND date=?
            """,
            (
                user_id,
                get_today(),
            ),
        )

        row = cursor.fetchone()

    finally:
        conn.close()

    if not row:
        return {
            "messages": 0,
            "images": 0,
            "code_requests": 0,
            "searches": 0,
        }

    return {
        "messages": int(row[0] or 0),
        "images": int(row[1] or 0),
        "code_requests": int(row[2] or 0),
        "searches": int(row[3] or 0),
    }


def add_usage(
    user_id,
    feature,
    amount=1,
):
    """
    Raw usage increment.

    This function intentionally does not check plan limits
    or cooldown. Strict request enforcement belongs to
    check_and_increment_usage().
    """

    feature = str(
        feature or ""
    ).strip().lower()

    if feature not in FEATURE_COLUMN_MAP:
        raise ValueError(
            f"Unknown feature: {feature}"
        )

    try:
        amount = int(amount)
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "amount must be an integer"
        )

    if amount <= 0:
        raise ValueError(
            "amount must be greater than zero"
        )

    column = FEATURE_COLUMN_MAP[feature]
    today = get_today()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            INSERT INTO usage(
                user_id,
                date,
                messages,
                images,
                code_requests,
                searches
            )
            VALUES(
                ?, ?,
                ?, ?, ?, ?
            )
            ON CONFLICT(user_id, date)
            DO UPDATE SET
                messages=usage.messages + excluded.messages,
                images=usage.images + excluded.images,
                code_requests=usage.code_requests + excluded.code_requests,
                searches=usage.searches + excluded.searches
            """,
            (
                user_id,
                today,
                amount if column == "messages" else 0,
                amount if column == "images" else 0,
                amount if column == "code_requests" else 0,
                amount if column == "searches" else 0,
            ),
        )

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def _get_last_request(
    cursor,
    user_id,
):
    cursor.execute(
        """
        SELECT last_request
        FROM rate_limit
        WHERE user_id=?
        """,
        (
            user_id,
        ),
    )

    row = cursor.fetchone()

    if not row:
        return 0.0

    try:
        return float(row[0] or 0)

    except (
        TypeError,
        ValueError,
    ):
        return 0.0


def _set_last_request(
    cursor,
    user_id,
    timestamp,
):
    cursor.execute(
        """
        INSERT INTO rate_limit(
            user_id,
            last_request
        )
        VALUES(?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            last_request=excluded.last_request
        """,
        (
            user_id,
            float(timestamp),
        ),
    )


def check_and_increment_usage(
    user_id,
    feature,
    limit,
    amount=1,
    cooldown_seconds=0,
):
    """
    Atomically enforce daily usage and optional cooldown.

    Returns:
        True:
            Request is allowed and usage is consumed.

        False:
            Request is rejected because the daily limit or
            cooldown was exceeded.
    """

    feature = str(
        feature or ""
    ).strip().lower()

    if feature not in FEATURE_COLUMN_MAP:
        raise ValueError(
            f"Unknown feature: {feature}"
        )

    try:
        amount = int(amount)
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "amount must be an integer"
        )

    if amount <= 0:
        raise ValueError(
            "amount must be greater than zero"
        )

    try:
        limit = int(limit)
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "limit must be an integer"
        )

    if limit < 0:
        raise ValueError(
            "limit must be zero or greater"
        )

    try:
        cooldown_seconds = float(
            cooldown_seconds or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "cooldown_seconds must be numeric"
        )

    if cooldown_seconds < 0:
        raise ValueError(
            "cooldown_seconds must be zero or greater"
        )

    if amount > limit:
        return False

    column = FEATURE_COLUMN_MAP[feature]
    usage_index = USAGE_COLUMNS[column]
    today = get_today()

    now = datetime.now().timestamp()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        # SQLite: serialize writers so cooldown + usage
        # are evaluated as one atomic operation.
        cursor.execute(
            "BEGIN IMMEDIATE"
        )

        # ==========================================
        # Cooldown
        # ==========================================

        if cooldown_seconds > 0:
            last_request = _get_last_request(
                cursor,
                user_id,
            )

            if (
                last_request > 0
                and now - last_request < cooldown_seconds
            ):
                conn.rollback()
                return False

        # ==========================================
        # Current daily usage
        # ==========================================

        cursor.execute(
            """
            SELECT
                messages,
                images,
                code_requests,
                searches
            FROM usage
            WHERE user_id=?
            AND date=?
            """,
            (
                user_id,
                today,
            ),
        )

        row = cursor.fetchone()

        if not row:
            cursor.execute(
                """
                INSERT INTO usage(
                    user_id,
                    date,
                    messages,
                    images,
                    code_requests,
                    searches
                )
                VALUES(
                    ?, ?,
                    0, 0, 0, 0
                )
                """,
                (
                    user_id,
                    today,
                ),
            )

            current = 0

        else:
            current = int(
                row[usage_index] or 0
            )

        # ==========================================
        # Daily limit
        # ==========================================

        if current + amount > limit:
            conn.rollback()
            return False

        # ==========================================
        # Consume usage
        # ==========================================

        cursor.execute(
            f"""
            UPDATE usage
            SET {column} = {column} + ?
            WHERE user_id=?
            AND date=?
            """,
            (
                amount,
                user_id,
                today,
            ),
        )

        # ==========================================
        # Save request timestamp
        # ==========================================

        _set_last_request(
            cursor,
            user_id,
            now,
        )

        conn.commit()
        return True

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()


def get_remaining_usage(
    user_id,
    feature,
    limit,
):
    """
    Return remaining daily usage for a feature.
    """

    feature = str(
        feature or ""
    ).strip().lower()

    if feature not in FEATURE_COLUMN_MAP:
        raise ValueError(
            f"Unknown feature: {feature}"
        )

    try:
        limit = int(limit)

    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "limit must be an integer"
        )

    usage = get_usage(
        user_id
    )

    column = FEATURE_COLUMN_MAP[feature]

    used = int(
        usage.get(
            column,
            0,
        )
        or 0
    )

    return max(
        0,
        limit - used,
    )


class UsageService:

    @staticmethod
    def get_user_usage(
        user_id,
    ):
        return get_usage(
            user_id
        )

    @staticmethod
    def add_user_usage(
        user_id,
        feature,
        amount=1,
    ):
        return add_usage(
            user_id,
            feature,
            amount,
        )

    @staticmethod
    def check_and_consume(
        user_id,
        feature,
        limit,
        amount=1,
        cooldown_seconds=0,
    ):
        return check_and_increment_usage(
            user_id,
            feature,
            limit,
            amount,
            cooldown_seconds,
        )

    @staticmethod
    def get_remaining(
        user_id,
        feature,
        limit,
    ):
        return get_remaining_usage(
            user_id,
            feature,
            limit,
        )