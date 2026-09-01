from services.billing.payment_service import (
    create_payment,
    approve_payment,
    reject_payment,
)

from database.db import (
    get_payment_request,
    get_all_payment_requests,
    init_db,
    add_user,
)


def setup_user(user_id):

    init_db()

    add_user(
        user_id,
        f"user{user_id}",
        None
    )


def test_create_payment():

    setup_user(100)

    payment = create_payment(
        100,
        "pro",
        30
    )

    assert payment is not None
    assert payment["plan"] == "pro"
    assert payment["amount"] == 300000


def test_duplicate_pending_payment():

    setup_user(101)

    p1 = create_payment(
        101,
        "pro",
        30
    )

    p2 = create_payment(
        101,
        "pro",
        30
    )

    assert p1["id"] == p2["id"]


def test_admin_approve_payment():

    setup_user(102)

    payment = create_payment(
        102,
        "pro",
        30
    )

    result = approve_payment(
        payment["id"]
    )

    assert result is True

    saved = get_payment_request(
        payment["id"]
    )

    assert saved["status"] == "paid"


def test_admin_reject_payment():

    setup_user(103)

    payment = create_payment(
        103,
        "pro",
        30
    )

    result = reject_payment(
        payment["id"]
    )

    assert result is True

    saved = get_payment_request(
        payment["id"]
    )

    assert saved["status"] == "failed"


def test_payment_history():

    payments = get_all_payment_requests(
        limit=10
    )

    assert isinstance(
        payments,
        list
    )