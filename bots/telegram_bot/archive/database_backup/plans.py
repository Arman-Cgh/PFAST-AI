from database.db import get_connection
from services.billing.subscription_service import get_subscription


# ==========================
# User plan resolution
# ==========================

def get_user_plan(user_id):
    """Return the effective plan name for a user, considering subscriptions."""
    subscription = get_subscription(user_id)
    if subscription.get("is_active"):
        return subscription["plan"]

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT plan
        FROM users
        WHERE id=?
        """,
        (user_id,)
    )
    row = cursor.fetchone()
    conn.close()

    if row and row[0]:
        stored_plan = row[0]
        if (
            subscription.get("status") in ["expired", "cancelled"]
            and subscription.get("plan") == stored_plan
        ):
            return "free"
        return stored_plan

    return "free"


# ==========================
# Plans API (centralized access to `plans` table)
# ==========================


def _get_plan_columns():
    """Return list of column names in plans table."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(plans)")
    cols = [row[1] for row in cursor.fetchall()]
    conn.close()
    return cols


def get_all_plans():
    """Return all plans as a dict: { plan_name: {col: value, ...}, ... }"""
    cols = _get_plan_columns()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM plans")
    rows = cursor.fetchall()
    result = {}
    for row in rows:
        row_dict = dict(zip(cols, row))
        name = row_dict.get("name")
        if name:
            result[name] = row_dict
    conn.close()
    return result


def get_plan(plan_name):
    """Return plan row as dict for plan_name. If not found, return {}."""
    cols = _get_plan_columns()
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT * FROM plans WHERE name=?", (plan_name,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return {}
    return dict(zip(cols, row))


def get_user_limits(user_id):
    """Return a dict of limits for the user's plan.

    This returns all columns available in the plans row for the user's plan
    (except internal id). Callers should interpret the keys appropriately.
    If the plan row is not found, returns reasonable defaults.
    """
    plan_name = get_user_plan(user_id)
    plan = get_plan(plan_name)

    # If plan missing, provide safe defaults (backward compatibility)
    if not plan:
        return {
            "daily_messages": 30,
            "daily_images": 1,
            "daily_technical_questions": 3,
            "cooldown_seconds": 5
        }

    # Remove internal fields that are not limits
    plan.pop("id", None)
    plan.pop("name", None)

    return plan


def update_plan(plan_name, values: dict):
    """Update plan columns with given values.

    Rules:
    - Only columns that already exist in the `plans` table may be updated.
    - No schema changes (no ALTER TABLE) will be performed here.
    - Numeric fields are validated for integer input (see numeric_keys set).

    Returns (True, message) on success or (False, error_message) on failure.
    """
    if not isinstance(values, dict) or not values:
        return False, "No values provided"

    cols = _get_plan_columns()
    # Disallow updating primary identifiers
    immutable = {"id", "name"}

    numeric_keys = {
        "daily_messages",
        "daily_images",
        "daily_technical_questions",
        "cooldown_seconds"
    }

    # Validate keys
    update_pairs = []
    params = []
    for key, val in values.items():
        if key in immutable:
            return False, f"Cannot update protected column: {key}"
        if key not in cols:
            return False, f"Unknown column: {key}"
        # Numeric validation
        if key in numeric_keys:
            try:
                # Ensure val is an integer (reject strings with emoji/non-digit chars)
                if isinstance(val, str):
                    # strip whitespace
                    vstr = val.strip()
                else:
                    vstr = str(val)
                # reject if contains non-digit and non-sign characters
                if not vstr.lstrip("+-").isdigit():
                    return False, f"Invalid integer for {key}: {val}"
                intval = int(vstr)
                params.append(intval)
            except Exception:
                return False, f"Invalid integer for {key}: {val}"
        else:
            # For non-numeric fields accept as-is
            params.append(val)
        update_pairs.append(f"{key} = ?")

    if not update_pairs:
        return False, "No valid columns to update"

    sql = f"UPDATE plans SET {', '.join(update_pairs)} WHERE name = ?"
    params.append(plan_name)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, tuple(params))
        conn.commit()
        conn.close()
        return True, "Plan updated"
    except Exception as e:
        try:
            conn.close()
        except Exception:
            pass
        return False, f"Database error: {e}"
