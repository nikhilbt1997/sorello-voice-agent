"""
Payment module — Stripe payment link generation and webhook handling.
Order only reaches the restaurant after payment is confirmed.
"""

import os
import json
import hmac
import hashlib
from datetime import datetime

import stripe
from fastapi import Request, HTTPException


def get_stripe_client():
    stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")
    return stripe


async def create_payment_link(
    order_text: str,
    call_sid: str,
    caller: str,
) -> dict:
    """
    Creates a Stripe payment link for the order and sends it via SMS.
    Returns the payment link URL and session ID.
    """
    client = get_stripe_client()

    if not stripe.api_key:
        # No Stripe key configured — skip payment for demo mode
        print("[DEMO MODE] No Stripe key — skipping payment step")
        return {
            "status": "demo_mode",
            "payment_link": None,
            "session_id": f"demo_{call_sid}",
        }

    try:
        # Create a Stripe Checkout session
        session = client.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "gbp",
                    "product_data": {
                        "name": "Restaurant Order",
                        "description": order_text[:100],  # truncate for display
                    },
                    "unit_amount": 0,  # Set to 0 for demo — real price from POS
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{os.environ.get('BASE_URL', 'https://sorello.io')}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{os.environ.get('BASE_URL', 'https://sorello.io')}/payment/cancel",
            metadata={
                "call_sid": call_sid,
                "caller": caller,
                "order": order_text[:500],
            },
        )

        return {
            "status": "created",
            "payment_link": session.url,
            "session_id": session.id,
        }

    except Exception as e:
        print(f"[ERROR] Stripe session creation failed: {e}")
        return {"status": "failed", "error": str(e)}


async def send_payment_sms(
    payment_link: str,
    caller: str,
    order_text: str,
) -> dict:
    """
    Sends the payment link to the customer via SMS using Twilio.
    """
    from twilio.rest import Client

    account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
    auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
    from_number = os.environ.get("TWILIO_PHONE_NUMBER")

    if not all([account_sid, auth_token, from_number]):
        print("[WARNING] Twilio not configured for SMS")
        return {"status": "skipped"}

    try:
        client = Client(account_sid, auth_token)
        message = client.messages.create(
            to=caller,
            from_=from_number,
            body=(
                f"Hi! Your order has been received.\n\n"
                f"Order: {order_text[:100]}\n\n"
                f"Please complete payment here:\n{payment_link}\n\n"
                f"Your order will be sent to the kitchen once payment is confirmed."
            ),
        )
        print(f"[INFO] Payment SMS sent: {message.sid}")
        return {"status": "sent", "sid": message.sid}

    except Exception as e:
        print(f"[ERROR] Payment SMS failed: {e}")
        return {"status": "failed", "error": str(e)}


async def verify_stripe_webhook(request: Request) -> dict:
    """
    Verifies Stripe webhook signature and returns the event.
    """
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    if not webhook_secret:
        # Demo mode — skip signature verification
        try:
            return json.loads(payload)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid payload")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, webhook_secret
        )
        return event
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")
