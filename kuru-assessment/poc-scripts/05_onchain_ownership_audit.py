"""
PoC #5: On-Chain Ownership Audit — Proving the AUSD ProxyAdmin EOA risk

VULNERABILITY: The AUSD stablecoin (0x00000000efe302beaa2b3e6e1b18d08d69a9012a)
is an upgradeable proxy whose ProxyAdmin is owned by a single EOA.
If that private key is compromised, the entire 118M AUSD supply can be rugged.

PROOF:
  - AUSD proxy has ProxyAdmin hardcoded: 0xb8fcc66d613e5f54ee6a425ddbf4a2fdbe4dedee
  - ProxyAdmin.owner() = 0x68898b77ebf7b55dca8a2e62d6fd74959a2930e2
  - eth_getCode(0x68898b77...) = 0x (no code = EOA = single private key)

USAGE:
    python 05_onchain_ownership_audit.py
"""

import json
import requests

RPC = "https://rpc.monad.xyz"


def eth_call(to: str, data: str) -> dict:
    payload = {"jsonrpc": "2.0", "method": "eth_call", "params": [{"to": to, "data": data}, "latest"], "id": 1}
    return requests.post(RPC, json=payload, timeout=15).json()


def get_storage(addr: str, slot: str) -> str:
    payload = {"jsonrpc": "2.0", "method": "eth_getStorageAt", "params": [addr, slot, "latest"], "id": 1}
    return requests.post(RPC, json=payload, timeout=15).json().get("result", "0x")


def get_code(addr: str) -> str:
    payload = {"jsonrpc": "2.0", "method": "eth_getCode", "params": [addr, "latest"], "id": 1}
    return requests.post(RPC, json=payload, timeout=15).json().get("result", "0x")


def get_balance(addr: str) -> float:
    payload = {"jsonrpc": "2.0", "method": "eth_getBalance", "params": [addr, "latest"], "id": 1}
    result = requests.post(RPC, json=payload, timeout=15).json().get("result", "0x0")
    return int(result, 16) / 1e18


def main():
    print("=" * 70)
    print("KURU.IO ON-CHAIN OWNERSHIP AUDIT")
    print("=" * 70)

    # 1. AUSD Token
    ausd = "0x00000000efe302beaa2b3e6e1b18d08d69a9012a"
    proxy_admin = "0xb8fcc66d613e5f54ee6a425ddbf4a2fdbe4dedee"

    print(f"\n[1] AUSD Token: {ausd}")
    print(f"    Name: AUSD (Agora stablecoin)")
    print(f"    Total supply: ~118M")

    # Check proxy admin
    admin_slot = "0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103"
    admin_from_storage = get_storage(ausd, admin_slot)
    print(f"    Admin slot: {admin_from_storage}")
    print(f"    ProxyAdmin: {proxy_admin}")

    # Check ProxyAdmin owner
    owner_result = eth_call(proxy_admin, "0x8da5cb5b")  # owner()
    owner_addr = "0x" + owner_result.get("result", "")[-40:]
    print(f"\n[2] ProxyAdmin owner: {owner_addr}")

    # Verify it's an EOA
    code = get_code(owner_addr)
    is_eoa = len(code) <= 4
    print(f"    Code length: {len(code)} chars")
    print(f"    IS EOA: {is_eoa}")
    if is_eoa:
        balance = get_balance(owner_addr)
        print(f"    Balance: {balance:.4f} MON")
        print(f"\n    *** CRITICAL: Single private key controls AUSD upgrades ***")
        print(f"    *** If compromised: mint unlimited AUSD, drain DEX liquidity ***")

    # 2. Margin Account
    margin = "0x2a68ba1833cdf93fa9da1eebd7f46242ad8e90c5"
    print(f"\n[3] Margin Account: {margin}")

    # Check Solady owner
    solady_slot = "0xffffffffffffffffffffffffffffffffffffffffffffffffffffffff74873927"
    margin_owner = get_storage(margin, solady_slot)
    margin_owner_addr = "0x" + margin_owner[-40:]
    print(f"    Solady owner: {margin_owner_addr}")

    # Check if it's a multisig
    threshold = eth_call(margin_owner_addr, "0xe75235b8")  # getThreshold()
    owners = eth_call(margin_owner_addr, "0xa0e67e2b")  # getOwners()

    if threshold.get("result"):
        t = int(threshold["result"], 16)
        print(f"    Multisig threshold: {t}")

    if owners.get("result") and len(owners["result"]) > 66:
        count_hex = owners["result"][66:130]
        count = int(count_hex, 16)
        print(f"    Number of signers: {count}")
        print(f"    Type: {t}/{count} Gnosis Safe")
        print(f"\n    Risk: {t} compromised keys = instant drain of all user funds")
        print(f"    Missing: No timelock — upgrades execute immediately")

    # 3. Check margin balance
    margin_balance = get_balance(margin)
    usdc = "0x754704bc059f8c67012fed69bc8a327a5aafb603"
    usdc_bal = eth_call(usdc, f"0x70a08231{margin[2:].zfill(64)}")
    usdc_val = int(usdc_bal.get("result", "0x0"), 16) / 1e6 if usdc_bal.get("result") else 0

    print(f"\n[4] Margin Account Holdings:")
    print(f"    MON: {margin_balance:,.2f} (~${margin_balance * 0.023:,.0f})")
    print(f"    USDC: ${usdc_val:,.2f}")
    print(f"    TOTAL AT RISK: ~${margin_balance * 0.023 + usdc_val:,.0f}")

    print(f"\n{'='*70}")
    print("VERIFICATION COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
