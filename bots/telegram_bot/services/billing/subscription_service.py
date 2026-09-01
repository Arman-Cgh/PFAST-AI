from datetime import date, datetime, timedelta

from database.db import get_connection


VALID_STATUSES = {
    "inactive",
    "active",
    "expired",
    "cancelled",
}


def _normalize_plan_name(plan_name):
    return (
        str(plan_name or "free")
        .strip()
        .lower()
    )


def _normalize_days(days):
    try:
        days = int(days)
    except (
        TypeError,
        ValueError,
    ):
        raise ValueError(
            "Subscription duration must be an integer."
        )

    if days < 0:
        raise ValueError(
            "Subscription duration cannot be negative."
        )

    return days


def _calculate_subscription_dates(
    start_date,
    duration_days,
):
    if not start_date:
        return "", 0, False

    try:
        start_date_obj = datetime.fromisoformat(
            str(start_date)
        ).date()

    except (
        TypeError,
        ValueError,
    ):
        return "", 0, False

    end_date_obj = (
        start_date_obj
        + timedelta(days=duration_days)
    )

    today = date.today()

    days_remaining = max(
        0,
        (
            end_date_obj - today
        ).days,
    )

    is_active = (
        duration_days > 0
        and today < end_date_obj
    )

    return (
        end_date_obj.isoformat(),
        days_remaining,
        is_active,
    )


# ==========================================================
# Create / Update Subscription
# ==========================================================

def create_subscription(
    user_id,
    plan_name,
    days,
):
    plan_name = _normalize_plan_name(
        plan_name
    )

    days = _normalize_days(
        days
    )

    if plan_name == "free":
        status = "inactive"
    else:
        if days <= 0:
            raise ValueError(
                "Paid subscriptions must have a positive duration."
            )

        status = "active"

    start_date = (
        datetime.now()
        .date()
        .isoformat()
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT plan
            FROM subscriptions
            WHERE user_id=?
            """,
            (
                user_id,
            ),
        )

        exists = cursor.fetchone()

        if exists:
            cursor.execute(
                """
                UPDATE subscriptions
                SET
                    plan=?,
                    start_date=?,
                    duration_days=?,
                    status=?
                WHERE user_id=?
                """,
                (
                    plan_name,
                    start_date,
                    days,
                    status,
                    user_id,
                ),
            )

        else:
            cursor.execute(
                """
                INSERT INTO subscriptions(
                    user_id,
                    plan,
                    start_date,
                    duration_days,
                    status
                )
                VALUES(?,?,?,?,?)
                """,
                (
                    user_id,
                    plan_name,
                    start_date,
                    days,
                    status,
                ),
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return get_subscription(
        user_id
    )


# ==========================================================
# Get Subscription
# ==========================================================

def get_subscription(
    user_id,
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                plan,
                start_date,
                duration_days,
                status
            FROM subscriptions
            WHERE user_id=?
            """,
            (
                user_id,
            ),
        )

        row = cursor.fetchone()

    finally:
        conn.close()

    if not row:
        return {
            "plan": "free",
            "status": "inactive",
            "duration_days": 0,
            "start_date": "",
            "end_date": "",
            "days_remaining": 0,
            "is_active": False,
        }

    plan_name = _normalize_plan_name(
        row[0]
    )

    start_date = row[1] or ""

    try:
        duration_days = max(
            0,
            int(row[2] or 0),
        )

    except (
        TypeError,
        ValueError,
    ):
        duration_days = 0

    stored_status = str(
        row[3] or "inactive"
    ).strip().lower()

    if stored_status not in VALID_STATUSES:
        stored_status = "inactive"

    end_date, days_remaining, date_is_active = (
        _calculate_subscription_dates(
            start_date,
            duration_days,
        )
    )

    is_active = (
        stored_status == "active"
        and date_is_active
        and plan_name != "free"
    )

    status = stored_status

    if (
        stored_status == "active"
        and not is_active
    ):
        status = "expired"

    return {
        "plan": plan_name,
        "start_date": start_date,
        "duration_days": duration_days,
        "status": status,
        "end_date": end_date,
        "days_remaining": days_remaining,
        "is_active": is_active,
    }


# ==========================================================
# Check Active
# ==========================================================

def is_subscription_active(
    user_id,
):
    data = get_subscription(
        user_id
    )

    return bool(
        data.get("is_active")
    )


# ==========================================================
# Cancel Subscription
# ==========================================================

def cancel_subscription(
    user_id,
):
    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            UPDATE subscriptions
            SET status='cancelled'
            WHERE user_id=?
            """,
            (
                user_id,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

def grant_temporary_subscription(
    user_id,
    plan_name,
    days,
):
    """
    Grant a temporary subscription reward without changing
    the user's permanent/base plan.

    If the user already has an active subscription, the reward
    is appended after the current subscription instead of
    destroying the existing paid period.
    """

    plan_name = _normalize_plan_name(
        plan_name
    )

    days = _normalize_days(
        days
    )

    if plan_name == "free":
        raise ValueError(
            "Temporary reward subscription cannot be free."
        )

    if days <= 0:
        raise ValueError(
            "Reward duration must be greater than zero."
        )

    today = date.today()

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT
                plan,
                start_date,
                duration_days,
                status
            FROM subscriptions
            WHERE user_id=?
            """,
            (
                user_id,
            ),
        )

        row = cursor.fetchone()

        start_date = today
        duration_days = days

        if row:
            current_plan = _normalize_plan_name(
                row[0]
            )

            current_start = row[1] or ""

            try:
                current_duration = max(
                    0,
                    int(row[2] or 0),
                )
            except (
                TypeError,
                ValueError,
            ):
                current_duration = 0

            current_status = str(
                row[3] or "inactive"
            ).strip().lower()

            current_end_date = None

            if current_start and current_duration > 0:
                try:
                    current_start_date = (
                        datetime.fromisoformat(
                            str(current_start)
                        ).date()
                    )

                    current_end_date = (
                        current_start_date
                        + timedelta(
                            days=current_duration
                        )
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    current_end_date = None

            current_is_active = (
                current_status == "active"
                and current_end_date is not None
                and today < current_end_date
            )

            if current_is_active:
                # Preserve an active subscription and append
                # the referral reward after its current expiry.
                start_date = current_end_date

                duration_days = days

                # If the existing subscription is already the
                # same plan, we can extend its total duration
                # without changing its base start date.
                if current_plan == plan_name:
                    start_date = (
                        current_start_date
                        if current_start_date
                        else today
                    )

                    duration_days = (
                        current_duration
                        + days
                    )

        cursor.execute(
            """
            INSERT INTO subscriptions(
                user_id,
                plan,
                start_date,
                duration_days,
                status
            )
            VALUES(?,?,?,?, 'active')
            ON CONFLICT(user_id)
            DO UPDATE SET
                plan=excluded.plan,
                start_date=excluded.start_date,
                duration_days=excluded.duration_days,
                status=excluded.status
            """,
            (
                user_id,
                plan_name,
                start_date.isoformat(),
                duration_days,
            ),
        )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        conn.close()

    return get_subscription(
        user_id
    )