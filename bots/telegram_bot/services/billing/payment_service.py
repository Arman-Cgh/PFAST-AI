from database.db import (
    create_payment_request,
    get_payment_request,
    get_pending_payment,
    get_plan_price,
    update_payment_request_status,
    update_user_plan,
)

from services.billing.gateway import (
    verify_payment as gateway_verify_payment,
)

from services.billing.subscription_service import (
    create_subscription,
)


VALID_PAYMENT_STATUSES = {
    "pending",
    "paid",
    "failed",
    "cancelled",
}

VALID_PLANS = {
    "free",
    "pro",
    "ultra",
}


def create_payment(
    user_id,
    plan_name,
    duration_days=30,
):
    plan_name = str(
        plan_name or ""
    ).strip().lower()

    duration_days = int(
        duration_days
    )

    if plan_name not in VALID_PLANS:
        return None

    if plan_name == "free":
        return None

    if duration_days <= 0:
        return None

    existing = get_pending_payment(
        user_id,
        plan_name,
    )

    if existing:
        return {
            "id": existing["id"],
            "plan": existing["plan_name"],
            "amount": existing["amount"],
            "currency": existing["currency"],
            "duration_days": existing["duration_days"],
        }

    price_data = get_plan_price(
        plan_name,
        duration_days,
    )

    if not price_data:
        return None

    if not price_data.get(
        "is_active",
        True,
    ):
        return None

    amount = int(
        price_data.get(
            "price",
            0,
        )
        or 0
    )

    if amount <= 0:
        return None

    payment_id = create_payment_request(
        user_id=user_id,
        plan_name=plan_name,
        amount=amount,
        currency=price_data.get(
            "currency",
            "IRR",
        ),
        duration_days=duration_days,
    )

    return {
        "id": payment_id,
        "plan": plan_name,
        "amount": amount,
        "currency": price_data.get(
            "currency",
            "IRR",
        ),
        "duration_days": duration_days,
    }


def get_payment(
    payment_id,
):
    return get_payment_request(
        payment_id
    )


def _activate_paid_payment(
    payment,
):
    if not payment:
        return False

    user_id = payment.get(
        "user_id"
    )

    plan_name = str(
        payment.get(
            "plan_name",
            "",
        )
    ).strip().lower()

    duration_days = int(
        payment.get(
            "duration_days",
            0,
        )
        or 0
    )

    if not user_id:
        return False

    if plan_name not in {
        "pro",
        "ultra",
    }:
        return False

    if duration_days <= 0:
        return False

    create_subscription(
        user_id,
        plan_name,
        duration_days,
    )

    update_user_plan(
        user_id,
        plan_name,
    )

    return True


def verify_payment(
    payment_id,
    authority,
):
    payment = get_payment_request(
        payment_id
    )

    if not payment:
        return False

    status = str(
        payment.get(
            "status",
            "",
        )
    ).strip().lower()

    if status == "paid":
        return True

    if status != "pending":
        return False

    authority = str(
        authority or ""
    ).strip()

    if not authority:
        return False

    if not gateway_verify_payment(
        authority
    ):
        return False

    if not _activate_paid_payment(
        payment
    ):
        return False

    update_payment_request_status(
        payment_id,
        "paid",
        authority,
    )

    return True


def approve_payment(
    payment_id,
):
    """
    Admin/manual approval.

    This intentionally does not call the external
    gateway verification layer.
    """

    payment = get_payment_request(
        payment_id
    )

    if not payment:
        return False

    status = str(
        payment.get(
            "status",
            "",
        )
    ).strip().lower()

    if status == "paid":
        return True

    if status != "pending":
        return False

    if not _activate_paid_payment(
        payment
    ):
        return False

    update_payment_request_status(
        payment_id,
        "paid",
        "admin",
    )

    return True


def reject_payment(
    payment_id,
):
    payment = get_payment_request(
        payment_id
    )

    if not payment:
        return False

    status = str(
        payment.get(
            "status",
            "",
        )
    ).strip().lower()

    if status != "pending":
        return False

    update_payment_request_status(
        payment_id,
        "failed",
        "admin",
    )

    return True