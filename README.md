# Sorello Voice Ordering Agent

A Twilio-powered AI voice agent that answers restaurant phone calls, takes orders, collects payment via Stripe, and only then sends a WhatsApp confirmation to the restaurant — no missed orders, no unpaid orders reaching the kitchen.

## Payment-First Flow

```
Customer calls restaurant number
        ↓
Voice agent greets and records order
        ↓
Stripe payment link sent to customer via SMS
        ↓
Customer pays
        ↓
Stripe webhook confirms payment
        ↓
WhatsApp sent to restaurant with order + PAID status
```

Nothing reaches the kitchen unpaid.

## How It Works

1. Customer calls the restaurant's Twilio number
2. Voice agent greets them with a consistent UK English voice (Amazon Polly Amy)
3. Customer speaks their order after the beep
4. Twilio transcribes the order automatically
5. Stripe payment link is created and sent to the customer via SMS
6. Customer completes payment on Stripe checkout
7. Stripe fires a webhook to `/payment/webhook`
8. Only after payment confirmation — a formatted WhatsApp message is sent to the restaurant

## Demo Mode

No Stripe key configured? The agent runs in demo mode — skips payment and sends WhatsApp directly. Useful for testing the voice flow without Stripe setup.

## Quick Start

### Prerequisites
- [Twilio account](https://www.twilio.com/) (free trial works)
- [Stripe account](https://stripe.com/) (free, test mode works)
- [ngrok](https://ngrok.com/) for local tunnelling
- Python 3.11+

### Setup

```bash
git clone https://github.com/nikhilbt1997/sorello-voice-agent
cd sorello-voice-agent
cp .env.example .env
# Fill in your credentials in .env
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### Expose with ngrok
```bash
ngrok http 8000
# Copy the https URL
```

### Configure Twilio
- Go to Twilio Console → Phone Numbers → your number
- Set Voice webhook to: `https://your-ngrok-url/voice/incoming`
- Method: POST

### Configure Stripe Webhook
- Go to Stripe Dashboard → Developers → Webhooks
- Add endpoint: `https://your-ngrok-url/payment/webhook`
- Event: `checkout.session.completed`
- Copy the webhook signing secret to `.env` as `STRIPE_WEBHOOK_SECRET`

### Test WhatsApp sandbox
- Go to Twilio Console → Messaging → Try it out → WhatsApp
- Send the join code to +1 415 523 8886 from your WhatsApp

## Project Structure

```
sorello-voice-agent/
├── app/
│   ├── main.py          # FastAPI app, routes, payment-first orchestration
│   ├── voice.py         # TwiML generation, transcription parsing, spam filter
│   ├── payment.py       # Stripe payment link creation, webhook verification
│   └── whatsapp.py      # WhatsApp/SMS order confirmation (fires after payment)
├── tests/
│   └── test_voice.py    # Unit tests
├── .env.example         # Environment variable template
├── docker-compose.yml   # Local development with Redis
├── Dockerfile           # Production container
└── requirements.txt
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/health` | GET | Health check |
| `/voice/incoming` | POST | Twilio inbound call — returns TwiML |
| `/voice/transcription` | POST | Twilio transcription callback — triggers payment link |
| `/payment/webhook` | POST | Stripe webhook — fires WhatsApp after payment confirmed |
| `/payment/success` | GET | Customer success page after payment |
| `/payment/cancel` | GET | Customer cancel page |

## Design Decisions

- **Payment-first** — WhatsApp to restaurant only fires after Stripe webhook confirms payment. No unpaid orders reach the kitchen.
- **Demo mode** — No Stripe key = skip payment, send WhatsApp directly. Easy to demo without Stripe setup.
- **Single consistent voice** — Amazon Polly Amy (UK English) for all interactions. Uniform brand experience.
- **Spam filtering** — Rule-based pre-filter kills robocalls and silent calls before any paid API is triggered.
- **WhatsApp → SMS fallback** — If WhatsApp delivery fails, automatically falls back to SMS. Restaurant always gets the order.
- **Stateless design** — Pending orders stored in-memory (Redis in production with TTL).

## Environment Variables

```env
TWILIO_ACCOUNT_SID=ACxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxx
TWILIO_PHONE_NUMBER=+1xxxxxxxxxx
TWILIO_WHATSAPP_NUMBER=+14155238886
RESTAURANT_WHATSAPP_NUMBER=+44xxxxxxxxx

# Leave blank to run in demo mode
STRIPE_SECRET_KEY=sk_test_xxxxxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxxxxx

RESTAURANT_NAME=Sorello Demo
BASE_URL=https://your-ngrok-url.ngrok-free.app
ENV=development
```

## Week 2 Roadmap

- POS adapter layer (Square, Lightspeed, Tevalis)
- Multi-turn conversation (upselling, clarification, allergy questions)
- Per-restaurant menu context injection
- Dashboard for call volume, conversion rate, payment success rate
- Multi-language support
