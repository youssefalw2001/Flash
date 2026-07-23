# kuru.io Security Assessment

**Date:** 2026-07-23
**Target:** https://kuru.io (On-chain orderbook DEX on Monad, Chain ID 143)
**Tools:** Str8Gold toolkit + custom probing

---

## Summary

Full security assessment of kuru.io covering web layer, API, WebSocket, and on-chain smart contracts.

### Critical Findings

| # | Finding | Impact | Exploitable Now? |
|---|---------|--------|-----------------|
| 1 | WebSocket IDOR — subscribe to any user's order/balance stream | Full trading surveillance, strategy theft | YES |
| 2 | AUSD ProxyAdmin owned by single EOA | 118M token supply rugpull if key compromised | Requires key theft |
| 3 | Margin account (3/5 Safe, no timelock) | $794K instant drain if 3 keys compromised | Requires key theft |
| 4 | API IDOR — margin balances readable for any address | Portfolio surveillance | YES |
| 5 | CORS wildcard + no rate limiting | Amplifies all above | YES |

### What Was Proven NOT Exploitable

- Cannot extract wallet private keys (Privy security holds)
- Cannot sign transactions with stolen JWT alone
- Cannot upgrade market contracts (ownership renounced)
- Cannot call creditUser from unauthorized addresses
- No SQL injection, no request smuggling

---

## Directory Structure

```
kuru-assessment/
├── README.md                  (this file)
├── reports/
│   ├── KURU_IO_ASSESSMENT.md         (full web + API report)
│   ├── KURU_IO_CRITICAL_ONCHAIN.md   (on-chain findings with exploit paths)
│   ├── sentinelscan.json             (raw scanner output)
│   ├── keyhunter.json                (crypto key validation)
│   ├── hydra.json                    (cache/smuggling audit)
│   ├── meridian.json                 (infrastructure graph)
│   └── wraith.json                   (auth bypass audit)
├── poc-scripts/
│   ├── 01_ws_idor_surveillance.py    (spy on any user's trades)
│   ├── 02_api_idor_portfolio.py      (read any user's balances)
│   ├── 03_maker_strategy_extraction.py (full maker intelligence)
│   ├── 04_frontrun_simulation.py     (front-running test + results)
│   └── 05_onchain_ownership_audit.py (verify proxy admin EOA risk)
```

---

## How to Run

```bash
pip install websockets requests pycryptodome eth-account

# Spy on any user (no auth needed)
python poc-scripts/01_ws_idor_surveillance.py 0xTARGET_ADDRESS

# Extract any user's portfolio (no auth needed)
python poc-scripts/02_api_idor_portfolio.py 0xTARGET_ADDRESS

# Full maker intelligence extraction
python poc-scripts/03_maker_strategy_extraction.py

# Front-running simulation (proves info leak, not guaranteed profit)
python poc-scripts/04_frontrun_simulation.py

# On-chain ownership verification
python poc-scripts/05_onchain_ownership_audit.py
```

---

## Key Results

### WebSocket IDOR (confirmed)
- Subscribe: `{"type":"subscribe","channel":"user","address":"<ANY_ADDRESS>"}`
- Returns: every order, cancel, fill, and balance update in real-time
- No authentication whatsoever

### Maker Intelligence (90 seconds of data)
- 3 active makers discovered
- $418K combined portfolio extracted via API IDOR
- Full strategy params: spread, refresh rate, fill rate, multi-market activity

### Front-Running (tested 3 times)
- Information leak confirmed
- Direct trading: NOT reliably profitable (48% win rate, negative EV)
- Real value: surveillance, strategy theft, competitive intelligence

### On-Chain (verified via Monad RPC)
- AUSD ProxyAdmin → EOA confirmed (single key = 118M at risk)
- Margin Account → 3/5 Safe, no timelock ($794K at risk)
- Market contracts → ownership renounced (safe, cannot be upgraded)

---

## Recommended Fixes (Priority Order)

1. **Add auth to WS `user` channel** — require wallet signature to subscribe
2. **Strip maker addresses from orderbook events** — show depth only
3. **Add timelock to margin Safe** — 48hr minimum
4. **Transfer AUSD ProxyAdmin to multisig + timelock**
5. **Add rate limiting** to all API endpoints
6. **Fix CORS** — replace `*` with explicit allowlist
