# Paymaster Gas Fee Findings — July 21, 2026

## Current On-Chain Balances (Verified)

| Chain | v0.6 Deposit | v0.7 Deposit | Total USD |
|-------|-------------|-------------|-----------|
| Base (8453) | 1.541 ETH ($5,394) | 0.939 ETH ($3,287) | $8,681 |
| Arbitrum (42161) | 0.616 ETH ($2,155) | 0.961 ETH ($3,365) | $5,520 |
| Optimism (10) | 0.497 ETH ($1,739) | 0.499 ETH ($1,747) | $3,486 |
| Polygon (137) | 0 POL | 0 POL | $0 (was ~$5,865) |
| Berachain (80094) | 14.98 BERA | 14.87 BERA | ~$200 |
| **TOTAL** | | | **~$17,887** |

## Key Details

- **API Key:** Exposed at `/app/api/pimlico/config` (no auth)
- **Also exposed at:** `auth.privy.io/api/v1/apps/cm6g13ap202c4wjq3ztwrneb9` (Privy public config)
- **Key status:** ACTIVE (confirmed returns gas prices)
- **Sponsorship policy:** GRANTS for ANY sender address, ANY calldata, ANY chain
- **Rate limiting:** NONE (50 simultaneous requests all succeeded)
- **Paymaster v0.6 address:** `0x6666666666667849c56f2850848cE1C4da65c68b`
- **Paymaster v0.7 address:** `0x777777777777AeC03fd955926DbF81597e66834C`
- **EntryPoint v0.6:** `0x5FF137D4b0FDCD49DcA30c7CF57E578a026d2789`
- **EntryPoint v0.7:** `0x0000000071727De22E5E9d8BAf0edAc6f37da032`

## Polygon Balance Missing

- Previous check: 7,484 POL (v0.6) + 5,549 POL (v0.7) = ~$5,865
- Current: $0 on both
- Status: Unknown — either drained externally or withdrawn by team
- Action needed: Check Pimlico dashboard activity logs

## Dual Exposure Problem

The key cannot be fixed by removing just the `/app/api/pimlico/config` endpoint. It is ALSO embedded in the Privy public app configuration at:

```
auth.privy.io/api/v1/apps/cm6g13ap202c4wjq3ztwrneb9
→ smart_wallet_config.configured_networks[*].paymaster_url
→ smart_wallet_config.configured_networks[*].bundler_url
```

Both must be rotated simultaneously.

## Remediation

1. Rotate key in Pimlico dashboard
2. Update key in Privy smart wallet config
3. Redeploy application
4. Add sponsorship policies in Pimlico:
   - Whitelist only approved Safe factory addresses
   - Restrict callData to app contract methods only
   - Set per-sender gas caps
   - Set global daily spending limits
5. Move key server-side — never expose to client
6. Check Pimlico billing logs for the full exposure period
