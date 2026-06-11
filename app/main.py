"""
Sorello Voice Ordering Agent
Payment-first flow: Call → Order → Payment Link → Payment Confirmed → WhatsApp to restaurant
"""

from fastapi import FastAPI, Request, Form
from fastapi.responses import Response
import uvicorn

from app.voice import handle_incoming_call, handle_transcription
from app.payment import create_payment_link, send_payment_sms, verify_stripe_webhook
from app.whatsapp import send_order_confirmation

# In-memory store for pending orders awaiting payment
# In production: use Redis with TTL
pending_orders: dict = {}

app = FastAPI(title="Sorello Voice Agent", version="0.2.0")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "sorello-voice-agent", "version": "0.2.0"}


@app.post("/voice/incoming")
async def incoming_call(request: Request):
    """
    Twilio calls this when a customer dials the restaurant number.
    Returns TwiML that greets the caller and records their order.
    """
    twiml = handle_incoming_call()
    return Response(content=twiml, media_type="application/xml")


@app.post("/voice/transcription")
async def transcription_callback(
    request: Request,
    TranscriptionText: str = Form(default=""),
    CallSid: str = Form(default=""),
    From: str = Form(default=""),
):
    """
    Twilio calls this after transcribing the caller's order.

    PAYMENT-FIRST FLOW:
    1. Parse the order
    2. Create a Stripe payment link
    3. Send payment link to customer via SMS
    4. Store order in pending_orders — waiting for payment confirmation
    5. WhatsApp to restaurant fires ONLY after payment webhook confirms
    """
    result = await handle_transcription(
        transcription=TranscriptionText,
        call_sid=CallSid,
        caller=From,
    )

    if not result.get("order"):
        return {"status": "skipped", "reason": result.get("error")}

    order_text = result["order"]

    # Step 1 — Create payment link
    payment_result = await create_payment_link(
        order_text=order_text,
        call_sid=CallSid,
        caller=From,
    )

    # Step 2 — Send payment link to customer via SMS
    if payment_result.get("payment_link"):
        await send_payment_sms(
            payment_link=payment_result["payment_link"],
            caller=From,
            order_text=order_text,
        )

    # Step 3 — Store order as PENDING payment
    session_id = payment_result.get("session_id", f"demo_{CallSid}")
    pending_orders[session_id] = {
        "order": order_text,
        "caller": From,
        "call_sid": CallSid,
        "status": "pending_payment",
    }

    # DEMO MODE: If no Stripe key, send WhatsApp immediately
    if payment_result.get("status") == "demo_mode":
        print("[DEMO MODE] Skipping payment — sending WhatsApp directly")
        await send_order_confirmation(
            order_text=order_text,
            caller=From,
            call_sid=CallSid,
        )
        return {"status": "demo_sent", "order": order_text}

    return {
        "status": "awaiting_payment",
        "session_id": session_id,
        "payment_link": payment_result.get("payment_link"),
    }


@app.post("/payment/webhook")
async def stripe_webhook(request: Request):
    """
    Stripe calls this when payment is completed.
    ONLY after payment confirmation do we send the order to the restaurant.
    """
    event = await verify_stripe_webhook(request)

    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        session_id = session["id"]
        metadata = session.get("metadata", {})

        # Retrieve the pending order
        pending = pending_orders.pop(session_id, None)

        if not pending:
            # Try to get from metadata directly
            order_text = metadata.get("order", "Order details unavailable")
            caller = metadata.get("caller", "Unknown")
            call_sid = metadata.get("call_sid", session_id)
        else:
            order_text = pending["order"]
            caller = pending["caller"]
            call_sid = pending["call_sid"]

        # Payment confirmed — NOW send to restaurant via WhatsApp
        print(f"[INFO] Payment confirmed for {session_id} — sending to restaurant")
        await send_order_confirmation(
            order_text=order_text,
            caller=caller,
            call_sid=call_sid,
            payment_confirmed=True,
        )

        return {"status": "processed"}

    return {"status": "ignored", "event_type": event.get("type")}


@app.get("/payment/success")
async def payment_success(session_id: str = ""):
    """Simple success page shown to customer after payment."""
    return {
        "status": "success",
        "message": "Payment confirmed! Your order is being prepared. Thank you.",
    }


@app.get("/payment/cancel")
async def payment_cancel():
    """Simple cancel page shown to customer if they cancel payment."""
    return {
        "status": "cancelled",
        "message": "Payment was cancelled. Please call back to place your order.",
    }


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
