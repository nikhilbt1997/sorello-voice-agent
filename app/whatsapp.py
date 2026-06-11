"""
WhatsApp and SMS order confirmation module.
Sends order details to the restaurant ONLY after payment is confirmed.
"""

import os
from datetime import datetime
from twilio.rest import Client


def get_twilio_client() -> Client:
    account_sid = os.environ["TWILIO_ACCOUNT_SID"]
    auth_token = os.environ["TWILIO_AUTH_TOKEN"]
    return Client(account_sid, auth_token)


def format_order_message(
    order_text: str,
    caller: str,
    call_sid: str,
    payment_confirmed: bool = False,
) -> str:
    """Formats a clean WhatsApp message for the restaurant."""
    timestamp = datetime.now().strftime("%d %b %Y, %H:%M")
    masked_caller = f"****{caller[-4:]}" if len(caller) >= 4 else "Unknown"
    payment_status = "✅ PAID" if payment_confirmed else "⚠️ UNPAID (Demo Mode)"

    return (
        f"🍽️ *New Order — Sorello*\n"
        f"──────────────────\n"
        f"🕐 *Time:* {timestamp}\n"
        f"📞 *Caller:* {masked_caller}\n"
        f"💳 *Payment:* {payment_status}\n"
        f"📋 *Order:*\n{order_text}\n"
        f"──────────────────\n"
        f"_Ref: {call_sid[-8:]}_"
    )


async def send_order_confirmation(
    order_text: str,
    caller: str,
    call_sid: str,
    payment_confirmed: bool = False,
) -> dict:
    """
    Sends the order as a WhatsApp message to the restaurant.
    In production this only fires after payment is confirmed.
    Falls back to SMS if WhatsApp fails.
    """
    restaurant_whatsapp = os.environ.get("RESTAURANT_WHATSAPP_NUMBER")
    sorello_whatsapp = os.environ.get("TWILIO_WHATSAPP_NUMBER")

    if not restaurant_whatsapp or not sorello_whatsapp:
        print("[WARNING] WhatsApp numbers not configured. Skipping send.")
        return {"status": "skipped", "reason": "missing_config"}

    message_body = format_order_message(
        order_text, caller, call_sid, payment_confirmed
    )

    try:
        client = get_twilio_client()
        message = client.messages.create(
            from_=f"whatsapp:{sorello_whatsapp}",
            to=f"whatsapp:{restaurant_whatsapp}",
            body=message_body,
        )
        print(f"[INFO] WhatsApp sent: {message.sid}")
        return {"status": "sent", "channel": "whatsapp", "sid": message.sid}

    except Exception as e:
        print(f"[ERROR] WhatsApp failed: {e}. Trying SMS fallback.")
        try:
            sms_body = (
                f"{'[PAID] ' if payment_confirmed else '[DEMO] '}"
                f"New Order:\n{order_text}\n"
                f"Caller: ****{caller[-4:]}\n"
                f"Ref: {call_sid[-8:]}"
            )
            client = get_twilio_client()
            message = client.messages.create(
                from_=os.environ["TWILIO_PHONE_NUMBER"],
                to=restaurant_whatsapp,
                body=sms_body,
            )
            print(f"[INFO] SMS fallback sent: {message.sid}")
            return {"status": "sent", "channel": "sms", "sid": message.sid}

        except Exception as sms_error:
            print(f"[ERROR] SMS fallback also failed: {sms_error}")
            return {"status": "failed", "error": str(sms_error)}
