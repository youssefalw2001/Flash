# kuru.io — CRITICAL On-Chain Security Findings

**Date:** 2026-07-23  
**Methodology:** Direct RPC probing of Monad mainnet (Chain ID 143)  
**Tools:** Custom contract analysis via eth_call, eth_getStorageAt, eth_getCode  

---

## TL;DR — What Can Steal Your Users' Money

A **single private key** (`0x68898b77ebf7b55dca8a2e62d6fd74959a2930e2`) can upgrade the AUSD stablecoin contract to a malicious implementation, mint unlimited AUSD, and dump it into the kuru.io orderbooks — draining all liquidity providers and margin depositors.

Additionally, **3 of 5 keys** on a Gnosis Safe control a margin account holding **~$794K** in user deposits with no timelock.

---

## FINDING 1: AUSD Stablecoin Upgradeable by Single EOA [CRITICAL]

### The Chain of Control

```
EOA (0x68898b77ebf7b55dca8a2e62d6fd74959a2930e2)
  │
  └── owns → ProxyAdmin (0xb8fcc66d613e5f54ee6a425ddbf4a2fdbe4dedee)
                │
                └── can call upgradeToAndCall() on → AUSD Token Proxy
                     (0x00000000efe302beaa2b3e6e1b18d08d69a9012a)
```

### Proof

1. **AUSD is a transparent proxy** with the ProxyAdmin address hardcoded:
   - Bytecode contains: `7f000000000000000000000000b8fcc66d613e5f54ee6a425ddbf4a2fdbe4dedee`
   - The contract checks `msg.sender == ProxyAdmin` and routes to `upgradeToAndCall`

2. **ProxyAdmin owner is an EOA:**
   - `ProxyAdmin.owner()` returns `0x68898b77ebf7b55dca8a2e62d6fd74959a2930e2`
   - `eth_getCode(0x68898b77...)` returns `0x` (no code = Externally Owned Account)

3. **AUSD is actively traded on kuru.io:**
   - Market address: `0x699abc15308156e9a3ab89ec7387e9cfe1c86a3b`
   - Last price: ~$1.00 (pegged stablecoin from Agora Finance)
   - Listed as `is_strict: true` — appears in default UI

4. **AUSD held in margin system:** 70,609.07 AUSD

### Exploit Path

```
1. Attacker compromises EOA private key (phishing, malware, insider)
2. EOA calls ProxyAdmin.upgrade(AUSD_proxy, malicious_implementation)
3. Malicious impl adds mint(address,uint256) callable by attacker
4. Attacker mints 100M AUSD
5. Attacker deposits AUSD into margin account
6. Attacker places market sell orders for AUSD → USDC
7. Legitimate LP orders filled with worthless minted AUSD
8. Attacker withdraws real USDC + MON
```

### Impact

- **Immediate:** All AUSD holders lose 100% of value
- **Secondary:** All USDC/MON liquidity on AUSD pairs drained
- **Tertiary:** If AUSD is used as collateral elsewhere, cascading liquidations

### Fix

1. **Transfer ProxyAdmin ownership to a multisig + timelock**
   ```
   ProxyAdmin.transferOwnership(timelocked_multisig)
   ```
2. **Add 48-hour timelock** on all upgrade operations
3. **Alternatively:** Renounce ProxyAdmin ownership entirely (freeze implementation forever)

---

## FINDING 2: Margin Account — 3/5 Multisig Without Timelock [HIGH]

### The Chain of Control

```
Gnosis Safe 3/5 (0x8b736dce2071783fd9db0a423dad17cc8ed5788b)
  Signers:
    1. 0xba0c215d77ab01015ea0bed931b412028157fe4b
    2. 0x32e00e1fe4c15803c65d4b3a10cb631e9e6d4b49
    3. 0xbf5657e6de2445b3f200bcfc54a1d489ae3d0b56
    4. 0x58af027eca44c810d714abd5bb087104e7c822cc
    5. 0x830b71f0481445392376acd6cfc7c35dc5db4a5a
  │
  └── owns (Solady) → Margin Account (0x2a68ba1833cdf93fa9da1eebd7f46242ad8e90c5)
                        │
                        └── Holds: 5,630,867 MON + 664,448 USDC (~$794K)
```

### Proof

1. **Margin account owner confirmed on-chain:**
   - Storage slot `0xffffffff...74873927` (Solady owner) = `0x8b736dce...`
   
2. **That address is a Gnosis Safe:**
   - `getThreshold()` = 3
   - `getOwners()` = 5 addresses (listed above)

3. **The margin account is a UUPS proxy:**
   - 141-byte proxy bytecode (standard UUPS pattern)
   - Implementation: `0x57cf97fe1fac7d78b07e7e0761410cb2e91f0ca7`
   - The owner can call `upgradeToAndCall` to change implementation

4. **Funds confirmed on-chain:**
   - `eth_getBalance(0x2a68ba...) = 5,630,866.76 MON`
   - `USDC.balanceOf(0x2a68ba...) = 664,447.95 USDC`

### Exploit Path

```
1. Compromise 3 of 5 Safe signer keys (phishing, social eng, insider)
2. Submit Safe tx: margin.upgradeToAndCall(malicious_impl, drain_calldata)
3. New impl transfers all MON + USDC to attacker
4. No timelock = instant execution, no user escape window
```

### Impact

- **All user deposits drained:** 5.6M MON + 664K USDC (~$794K at current prices)
- **Zero recovery window:** No timelock means users cannot withdraw before exploit executes

### Fix

1. **Add a timelock contract** (OpenZeppelin TimelockController, 48hr minimum)
2. **Set Safe as proposer, timelock as executor**
3. **Increase threshold** to 4/5 or add hardware wallet requirement
4. **Emit events** on all ownership/upgrade operations for monitoring

---

## FINDING 3: Market Contracts — Ownership Renounced (POSITIVE) ✓

The orderbook market contracts (e.g., `0x065c9d28...`) have:
- Solady owner = `address(0)` (renounced)
- Cannot be upgraded by anyone

**This is correct security practice.** No action needed.

---

## FINDING 4: WMON Contract (374M MON) — Not Vulnerable ✓

Contract `0x3bd359c1119da7da1d913d1c4d2b7c461115433a` is the **Wrapped MON (WMON)** canonical wrapper.
- No owner, no proxy
- 374M MON is just the total amount of wrapped MON across all users
- Standard WETH-pattern contract

**Not a vulnerability.** This is expected infrastructure.

---

## Architecture Diagram (On-Chain)

```
                    ┌────────────────────────────────┐
                    │  EOA 0x68898b77...             │
                    │  (SINGLE PRIVATE KEY)          │
                    └───────────────┬────────────────┘
                                    │ owns
                    ┌───────────────▼────────────────┐
                    │  ProxyAdmin 0xb8fcc66d...      │
                    └───────────────┬────────────────┘
                                    │ can upgrade
                    ┌───────────────▼────────────────┐
                    │  AUSD Token 0x000000...9012a   │
                    │  Supply: 118M | Price: $1.00   │
                    │  Actively traded on DEX        │
                    └────────────────────────────────┘

                    ┌────────────────────────────────┐
                    │  Gnosis Safe 3/5 0x8b736d...   │
                    │  (5 signers, threshold 3)      │
                    │  NO TIMELOCK                   │
                    └───────────────┬────────────────┘
                                    │ owns (Solady)
                    ┌───────────────▼────────────────┐
                    │  Margin Account 0x2a68ba...    │
                    │  5.6M MON + 664K USDC          │
                    │  (~$794K total)                │
                    │  ALL user margin deposits      │
                    └────────────────────────────────┘

                    ┌────────────────────────────────┐
                    │  Market Contracts              │
                    │  (ownership RENOUNCED ✓)       │
                    │  Cannot be upgraded            │
                    └────────────────────────────────┘
```

---

## Priority Remediation

| # | Action | Severity | Effort | Blocks |
|---|--------|----------|--------|--------|
| 1 | Transfer AUSD ProxyAdmin to multisig + timelock | CRITICAL | 2 hours | Nothing |
| 2 | Add 48hr timelock to margin account Safe | HIGH | 4 hours | Nothing |
| 3 | Increase Safe threshold to 4/5 | HIGH | 30 min | Nothing |
| 4 | Deploy on-chain monitoring for upgradeToAndCall events | HIGH | 1 day | Nothing |

---

## Verification Commands

Anyone can verify these findings with:

```python
# Verify AUSD ProxyAdmin owner is EOA
curl -X POST https://rpc.monad.xyz -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_call","params":[{"to":"0xb8fcc66d613e5f54ee6a425ddbf4a2fdbe4dedee","data":"0x8da5cb5b"},"latest"],"id":1}'
# Returns: ...68898b77ebf7b55dca8a2e62d6fd74959a2930e2

# Verify that address is EOA (no code)
curl -X POST https://rpc.monad.xyz -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getCode","params":["0x68898b77ebf7b55dca8a2e62d6fd74959a2930e2","latest"],"id":1}'
# Returns: "0x" (no code = EOA)

# Verify margin account balance
curl -X POST https://rpc.monad.xyz -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"eth_getBalance","params":["0x2a68ba1833cdf93fa9da1eebd7f46242ad8e90c5","latest"],"id":1}'
```
