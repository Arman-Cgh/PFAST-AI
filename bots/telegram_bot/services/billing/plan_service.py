from services.billing.subscription_service import (
    get_subscription,
)

from database.db import get_connection


DEFAULT_PLAN_LIMITS = {
    "daily_messages": 30,
    "daily_images": 1,
    "daily_technical_questions": 3,
    "cooldown_seconds": 5,
}


PLAN_INTERNAL_COLUMNS = {
    "id",
    "name",
}


def _normalize_plan_name(
    plan_name,
):
    return (
        str(plan_name or "free")
        .strip()
        .lower()
    )


def _get_plan_columns():
    """
    Return existing column names from the plans table.

    This is intentionally read-only. No schema mutation is
    performed here.
    """

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "PRAGMA table_info(plans)"
        )

        return [
            row[1]
            for row in cursor.fetchall()
        ]

    finally:
        conn.close()


# ==========================================================
# User Plan Resolution
# ==========================================================

def get_user_plan(
    user_id,
):
    """
    Resolve the effective plan.

    Priority:
        1. Valid active subscription.
        2. Stored users.plan.
        3. free.

    An expired/cancelled subscription does not override the
    user's stored base plan.
    """

    subscription = get_subscription(
        user_id
    )

    if subscription.get(
        "is_active"
    ):
        return _normalize_plan_name(
            subscription.get(
                "plan"
            )
        )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT plan
            FROM users
            WHERE id=?
            """,
            (
                user_id,
            ),
        )

        row = cursor.fetchone()

    finally:
        conn.close()

    if row and row[0]:
        return _normalize_plan_name(
            row[0]
        )

    return "free"


# ==========================================================
# Plans API
# ==========================================================

def get_all_plans():
    """
    Return all plans as:

        {
            "free": {...},
            "pro": {...},
            "ultra": {...},
        }
    """

    columns = _get_plan_columns()

    if not columns:
        return {}

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "SELECT * FROM plans"
        )

        rows = cursor.fetchall()

    finally:
        conn.close()

    result = {}

    for row in rows:
        plan = dict(
            zip(
                columns,
                row,
            )
        )

        name = plan.get(
            "name"
        )

        if name:
            result[
                _normalize_plan_name(name)
            ] = plan

    return result


def get_plan(
    plan_name,
):
    plan_name = _normalize_plan_name(
        plan_name
    )

    columns = _get_plan_columns()

    if not columns:
        return {}

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            """
            SELECT *
            FROM plans
            WHERE name=?
            """,
            (
                plan_name,
            ),
        )

        row = cursor.fetchone()

    finally:
        conn.close()

    if not row:
        return {}

    return dict(
        zip(
            columns,
            row,
        )
    )


# ==========================================================
# User Limits
# ==========================================================

def get_user_limits(
    user_id,
):
    """
    Return the configured limits of the effective user plan.
    """

    plan_name = get_user_plan(
        user_id
    )

    plan = get_plan(
        plan_name
    )

    if not plan:
        return dict(
            DEFAULT_PLAN_LIMITS
        )

    return {
        key: value
        for key, value in plan.items()
        if key not in PLAN_INTERNAL_COLUMNS
    }


# ==========================================================
# Update Plan
# ==========================================================

def update_plan(
    plan_name,
    values,
):
    """
    Update existing columns of an existing plan.

    This function never changes the database schema.
    """

    plan_name = _normalize_plan_name(
        plan_name
    )

    if not plan_name:
        return (
            False,
            "Invalid plan name",
        )

    if not isinstance(
        values,
        dict,
    ) or not values:
        return (
            False,
            "No values provided",
        )

    columns = _get_plan_columns()

    if not columns:
        return (
            False,
            "Plans table is unavailable",
        )

    update_pairs = []
    params = []

    for key, value in values.items():

        if key in PLAN_INTERNAL_COLUMNS:
            return (
                False,
                f"Cannot update protected column: {key}",
            )

        if key not in columns:
            return (
                False,
                f"Unknown column: {key}",
            )

        # Numeric limits are detected from the known plan
        # schema rather than maintaining another hardcoded
        # collection of possible fields.
        column_definition = None

        conn = get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "PRAGMA table_info(plans)"
            )

            schema_rows = cursor.fetchall()

        finally:
            conn.close()

        for schema_row in schema_rows:
            if schema_row[1] == key:
                column_definition = (
                    schema_row[2] or ""
                ).upper()
                break

        if column_definition and any(
            numeric_type in column_definition
            for numeric_type in (
                "INT",
                "REAL",
                "NUM",
                "DECIMAL",
            )
        ):
            try:
                if isinstance(
                    value,
                    bool,
                ):
                    raise ValueError

                if isinstance(
                    value,
                    str,
                ):
                    normalized = value.strip()

                    if not normalized:
                        raise ValueError

                    if not normalized.lstrip(
                        "+-"
                    ).isdigit():
                        raise ValueError

                    value = int(
                        normalized
                    )

                elif isinstance(
                    value,
                    (int, float),
                ):
                    value = int(
                        value
                    )

                else:
                    raise ValueError

            except (
                TypeError,
                ValueError,
            ):
                return (
                    False,
                    f"Invalid numeric value for {key}: {value}",
                )

            if value < 0:
                return (
                    False,
                    f"{key} cannot be negative",
                )

        update_pairs.append(
            f"{key}=?"
        )

        params.append(
            value
        )

    if not update_pairs:
        return (
            False,
            "No valid columns to update",
        )

    params.append(
        plan_name
    )

    sql = (
        "UPDATE plans SET "
        + ", ".join(update_pairs)
        + " WHERE name=?"
    )

    conn = get_connection()
    cursor = conn.cursor()

    try:
        cursor.execute(
            sql,
            tuple(params),
        )

        if cursor.rowcount == 0:
            conn.rollback()

            return (
                False,
                f"Plan '{plan_name}' not found",
            )

        conn.commit()

        return (
            True,
            "Plan updated",
        )

    except Exception as exc:
        conn.rollback()

        return (
            False,
            f"Database error: {exc}",
        )

    finally:
        conn.close()