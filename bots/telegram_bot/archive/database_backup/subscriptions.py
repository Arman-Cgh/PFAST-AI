from datetime import datetime, timedelta

from database.db import get_connection



# ==========================
# Create Subscription
# ==========================

def create_subscription(
    user_id,
    plan_name,
    days
):

    conn = get_connection()
    cursor = conn.cursor()


    start_date = datetime.now().date().isoformat()


    cursor.execute(
        """
        SELECT plan

        FROM subscriptions

        WHERE user_id=?

        """,
        (
            user_id,
        )
    )


    exists = cursor.fetchone()
    status = "inactive" if plan_name == "free" else "active"


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
                user_id
            )
        )


    else:

        cursor.execute(
            """
            INSERT INTO subscriptions

            (
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
                status
            )
        )


    conn.commit()
    conn.close()



# ==========================
# Get Subscription
# ==========================

def get_subscription(
    user_id
):

    conn = get_connection()
    cursor = conn.cursor()


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
        )
    )


    row = cursor.fetchone()


    conn.close()


    if not row:

        return {

            "plan": "free",

            "status": "inactive",

            "duration_days": 0,

            "start_date": "",

            "end_date": "",

            "days_remaining": 0,

            "is_active": False

        }


    plan, start_date, duration_days, status = row

    end_date = ""
    days_remaining = 0
    is_active = False

    if start_date:
        try:
            start_date_obj = datetime.fromisoformat(start_date).date()
            end_date_obj = start_date_obj + timedelta(days=duration_days)
            today = datetime.now().date()
            end_date = end_date_obj.isoformat()
            days_remaining = max(0, (end_date_obj - today).days)
            is_active = (
                status == "active"
                and duration_days > 0
                and today < end_date_obj
            )
            if status == "active" and days_remaining == 0:
                status = "expired"
        except ValueError:
            is_active = status == "active"

    return {

        "plan": plan,

        "start_date": start_date,

        "duration_days": duration_days,

        "status": status,

        "end_date": end_date,

        "days_remaining": days_remaining,

        "is_active": is_active

    }



# ==========================
# Check Active
# ==========================

def is_subscription_active(
    user_id
):

    data = get_subscription(
        user_id
    )


    return (
        data["status"] == "active"
    )



# ==========================
# Cancel Subscription
# ==========================

def cancel_subscription(
    user_id
):

    conn = get_connection()
    cursor = conn.cursor()


    cursor.execute(
        """
        UPDATE subscriptions

        SET status='cancelled'

        WHERE user_id=?

        """,
        (
            user_id,
        )
    )


    conn.commit()
    conn.close()