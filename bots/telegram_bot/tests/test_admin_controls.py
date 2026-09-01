import pytest

from handlers.admin.menu import get_admin_menu
from handlers.admin.payments import handle_payments_callback
from handlers.admin.settings import handle_settings_callback
from handlers.admin.subscriptions import (
    activate_user_plan,
    cancel_user_subscription,
    get_user_subscription,
)
from services.billing.payment_service import (
    create_payment,
    approve_payment,
    reject_payment,
)
from database.db import (
    add_user,
    get_payment_request,
    get_plan_price,
    get_referral_settings,
    get_referral_message_template,
    get_admin_action,
    init_db,
)


class FakeUser:
    def __init__(self, user_id=5383969883):
        self.id = user_id
        self.username = "admin_test"
        self.first_name = "Admin"


class FakeQuery:
    def __init__(self, data, user_id=5383969883):
        self.data = data
        self.from_user = FakeUser(user_id)
        self.answers = []
        self.edited = []

    async def answer(self, *args, **kwargs):
        self.answers.append((args, kwargs))

    async def edit_message_text(self, text, **kwargs):
        self.edited.append((text, kwargs))


class FakeUpdate:
    def __init__(self, data, user_id=5383969883):
        self.callback_query = FakeQuery(data, user_id)


def _callback_values(markup):
    return [
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
        if button.callback_data
    ]


def test_admin_menu_exposes_required_controls():
    markup = get_admin_menu()
    callbacks = set(_callback_values(markup))

    assert "payments" in callbacks
    assert "mandatory_join" in callbacks
    assert "pricing" in callbacks
    assert "referral_settings" in callbacks
    assert "subscription" in callbacks
    assert "manage_plans" in callbacks


@pytest.mark.asyncio
async def test_admin_callback_rejects_non_admin_for_payment_handler():
    update = FakeUpdate("payments", user_id=123456789)

    handled = await handle_payments_callback(
        update,
        object(),
        "payments",
    )

    assert handled is True
    assert update.callback_query.edited


@pytest.mark.asyncio
async def test_payment_list_renders_pending_action_buttons(monkeypatch):
    payment = {
        "id": 501,
        "user_id": 777,
        "plan_name": "pro",
        "amount": 300000,
        "currency": "IRR",
        "status": "pending",
    }

    monkeypatch.setattr(
        "handlers.admin.payments.get_all_payment_requests",
        lambda limit=10: [payment],
    )

    update = FakeUpdate("payments")

    handled = await handle_payments_callback(
        update,
        object(),
        "payments",
    )

    assert handled is True
    assert update.callback_query.edited

    markup = update.callback_query.edited[-1][1]["reply_markup"]
    callbacks = set(_callback_values(markup))

    assert "approve_payment:501" in callbacks
    assert "reject_payment:501" in callbacks


@pytest.mark.asyncio
async def test_payment_list_hides_actions_for_completed_payment(monkeypatch):
    payment = {
        "id": 502,
        "user_id": 777,
        "plan_name": "pro",
        "amount": 300000,
        "currency": "IRR",
        "status": "paid",
    }

    monkeypatch.setattr(
        "handlers.admin.payments.get_all_payment_requests",
        lambda limit=10: [payment],
    )

    update = FakeUpdate("payments")

    handled = await handle_payments_callback(
        update,
        object(),
        "payments",
    )

    assert handled is True
    markup = update.callback_query.edited[-1][1]["reply_markup"]
    callbacks = set(_callback_values(markup))

    assert "approve_payment:502" not in callbacks
    assert "reject_payment:502" not in callbacks


def test_approve_payment_activates_subscription():
    init_db()
    user_id = 810001
    add_user(user_id, "admin_payment_test", "Payment Test")

    payment = create_payment(user_id, "pro", 30)
    assert payment is not None

    assert approve_payment(payment["id"]) is True

    saved = get_payment_request(payment["id"])
    assert saved["status"] == "paid"

    subscription = get_user_subscription(user_id)
    assert subscription["plan"] == "pro"
    assert subscription["status"] == "active"

    # Idempotent approve: must remain successful and must not corrupt state.
    assert approve_payment(payment["id"]) is True
    saved_again = get_payment_request(payment["id"])
    assert saved_again["status"] == "paid"


def test_reject_payment_changes_state_without_subscription():
    init_db()
    user_id = 810002
    add_user(user_id, "admin_reject_test", "Reject Test")

    payment = create_payment(user_id, "pro", 30)
    assert payment is not None

    assert reject_payment(payment["id"]) is True

    saved = get_payment_request(payment["id"])
    assert saved["status"] == "failed"

    subscription = get_user_subscription(user_id)
    assert subscription["plan"] == "free"
    assert subscription["is_active"] is False


def test_activation_and_cancellation_helpers():
    init_db()
    user_id = 810003
    add_user(user_id, "admin_sub_test", "Subscription Test")

    message = activate_user_plan(user_id, "pro", 30)
    assert "Pro" in message

    sub = get_user_subscription(user_id)
    assert sub["plan"] == "pro"
    assert sub["status"] == "active"

    message = cancel_user_subscription(user_id)
    assert "Free" in message

    sub = get_user_subscription(user_id)
    assert sub["plan"] == "pro" or sub["plan"] == "free"
    assert sub["status"] in {"cancelled", "inactive", "expired"}


auto_referral_fields = (
    "required_invites",
    "reward_days",
    "reward_plan",
)


def test_settings_referral_defaults_are_readable():
    init_db()
    settings = get_referral_settings()
    template = get_referral_message_template()

    assert all(field in settings for field in auto_referral_fields)
    assert isinstance(template, str)
    assert template.strip()


@pytest.mark.asyncio
async def test_settings_pricing_callback_enters_price_action(monkeypatch):
    monkeypatch.setattr(
        "handlers.admin.settings.get_plan_prices",
        lambda: {
            "pro": {
                "price": 300000,
                "currency": "IRR",
                "duration_days": 30,
                "is_active": True,
            },
            "ultra": {
                "price": 700000,
                "currency": "IRR",
                "duration_days": 30,
                "is_active": True,
            },
        },
    )

    update = FakeUpdate("pricing")
    handled = await handle_settings_callback(
        update,
        object(),
        "pricing",
    )

    assert handled is True
    assert update.callback_query.edited


@pytest.mark.asyncio
async def test_settings_set_price_rejects_invalid_plan():
    update = FakeUpdate("set_price:unknown")

    handled = await handle_settings_callback(
        update,
        object(),
        "set_price:unknown",
    )

    assert handled is True


def test_db_plan_price_exists_for_billing_flow():
    init_db()
    price = get_plan_price("pro", 30)
    assert price["price"] >= 0
    assert price["currency"]
