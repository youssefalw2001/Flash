# Kuru DEX Intelligence Dashboard

**This is a vulnerability demonstration.** It shows what an attacker could build and sell using the unauthenticated WebSocket and API endpoints on kuru.io.

## What It Does

Connects to `wss://ws.kuru.io` and `api.kuru.io` — both without any authentication — and builds a real-time surveillance dashboard showing:

- Every active market maker's identity (wallet address)
- Their full portfolio (token balances, USD value)
- Their trading strategy (spread, refresh rate, fill rate)
- Their activity across all markets
- A live feed of every order, cancel, fill, and balance change

## Running It

```bash
cd kuru-intel-dashboard
pip install -r requirements.txt
python server.py
```

Then open http://localhost:8080

## Architecture

```
┌─────────────────────────────────┐
│   Browser (localhost:8080)       │
│   Polls /api/state every 2s     │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│   Python Server (aiohttp)       │
│   - Serves HTML dashboard       │
│   - Serves /api/state JSON      │
│   - Runs WS collector task      │
└──────────────┬──────────────────┘
               │
┌──────────────▼──────────────────┐
│   wss://ws.kuru.io              │
│   NO AUTH - subscribes to:      │
│   - orderbook (all makers)      │
│   - user/{address} (IDOR)       │
├─────────────────────────────────┤
│   https://api.kuru.io/api/v2    │
│   NO AUTH - reads:              │
│   - /margin/balances/{any_addr} │
└─────────────────────────────────┘
```

## The Vulnerability

1. **WebSocket IDOR:** `{"type":"subscribe","channel":"user","address":"<ANYONE>"}` returns all their trading activity
2. **API IDOR:** `GET /api/v2/margin/balances/{any_address}` returns full portfolio
3. **No rate limiting** on either endpoint
4. **CORS: \*** allows any website to query the API

## Fix

Add authentication to the WebSocket `user` channel — require a signed message proving wallet ownership before accepting the subscription.
