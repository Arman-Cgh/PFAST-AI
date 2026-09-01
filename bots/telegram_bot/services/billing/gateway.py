import os
from uuid import uuid4


PAYMENT_GATEWAY_MODE = os.getenv(
    "PAYMENT_GATEWAY_MODE",
    "manual",
).strip().lower()

PAYMENT_BASE_URL = os.getenv(
    "PAYMENT_BASE_URL",
    "",
).strip().rstrip("/")


def create_payment_link(
    payment_id,
    amount,
):
    """
    Create a payment link.

    Supported modes:

    manual:
        No automatic external gateway is assumed.
        A deterministic local reference is generated.

    external:
        Requires PAYMENT_BASE_URL.
        The actual payment provider integration must
        be implemented behind that URL.
    """

    payment_id = int(
        payment_id
    )

    amount = int(
        amount or 0
    )

    authority = str(
        uuid4()
    )

    if PAYMENT_GATEWAY_MODE == "external":
        if not PAYMENT_BASE_URL:
            raise RuntimeError(
                "PAYMENT_BASE_URL is required "
                "when PAYMENT_GATEWAY_MODE=external."
            )

        payment_url = (
            f"{PAYMENT_BASE_URL}/pay/"
            f"{authority}"
        )

        return {
            "authority": authority,
            "url": payment_url,
            "amount": amount,
            "mode": "external",
        }

    if PAYMENT_GATEWAY_MODE == "manual":
        return {
            "authority": authority,
            "url": "",
            "amount": amount,
            "mode": "manual",
        }

    raise ValueError(
        f"Unsupported PAYMENT_GATEWAY_MODE: "
        f"{PAYMENT_GATEWAY_MODE}"
    )


def verify_payment(
    authority,
):
    """
    Automatic verification is disabled until a real
    payment gateway integration is configured.

    Manual/admin approval is handled separately by
    payment_service.approve_payment().
    """

    if PAYMENT_GATEWAY_MODE != "external":
        return False

    if not authority:
        return False

    raise NotImplementedError(
        "Real payment gateway verification is not "
        "implemented yet."
    )