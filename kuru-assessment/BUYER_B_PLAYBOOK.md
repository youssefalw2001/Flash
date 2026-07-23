# Buyer B Playbook: Maximum Revenue From Kuru Intelligence Feed

**Context:** You are a competing DEX on Monad (like Composite, or a new entrant) buying this intelligence feed. Your goal: extract maximum value from the data to grow your own protocol at Kuru's expense.

---

## The Competitive Landscape

Kuru's competitors on Monad (confirmed via research):
- **Composite** — native DEX on Monad
- **Uniswap** — deployed on Monad, dominant in AMM volume
- **Curve** — deployed on Monad
- **0x** — building orderbook infrastructure on Monad
- **Zaros** — perp DEX expanding to Monad spot

Kuru's advantage: **first native CLOB DEX** on Monad, $13.6M in funding (Paradigm-led), first-mover on orderbook liquidity.

Kuru's weakness (what you exploit): **all maker intelligence is public via WS IDOR.**

---

## Attack Plan: Precision Vampire Attack

Classic vampire attacks (SushiSwap → Uniswap) are blunt — fork the code, offer higher yields, hope people migrate. They're expensive and often fail because the incentives run out.

This is a **precision vampire attack** — you use intelligence to surgically poach specific, named makers with custom offers. Zero waste.

---

## Phase 1: Intelligence Collection (Week 1)

From the dashboard, you now know:

| Maker | Portfolio | Refresh | Fills/day | Markets |
|-------|-----------|---------|-----------|---------|
| `0x2b46C08C...` | $66,888 | 596ms | ~9,600 | MON/USDC, XAUt0/USDC, BTC/USDC, +1 |
| `0xd0F8A642...` | $21,530 | 1,406ms | ~0 | MON/USDC |
| `0x8Cf67893...` | $330,127 | 4,737ms | ~20,160 | MON/USDC, WETH/USDC |

**Key insight:** Maker 3 (`0x8Cf6...`) has $330K in capital and gets the most fills. They're quoting tighter than the others (hence more fills) but refreshing slowly (4.7s). They're the best target — most capital, most flow, and their slow refresh means they're probably running on basic infrastructure that could be improved.

---

## Phase 2: Identify The People (Week 1-2)

Wallet `0x8Cf67893C236963233023B56AC56A185B042866F` — trace it:

1. **On-chain history:** Check Monad explorer for their first transactions. Where did their funds come from? Bridge from Ethereum? That gives you their ETH address.
2. **Cross-reference:** Check if the same address is active on other chains (Arbitrum, Base). Many makers use the same address everywhere.
3. **Social graph:** Tools like Arkham, Nansen, DeBank label addresses. If this is a known desk, you'll find them.
4. **Deposit source:** Their $330K came from somewhere. Track the funding tx back to a CEX withdrawal or bridge. CEX withdrawals sometimes correlate with known entities.
5. **Twitter/Discord:** Search the address on crypto Twitter. Makers sometimes post their addresses for airdrops, governance, or flex.

**Probability of identification:** 60-80% for professional desks. They don't hide well because they need to interact with protocols (claim rewards, governance, etc).

---

## Phase 3: The Pitch (Week 2-3)

Once identified, DM them. The pitch works because you have SPECIFIC numbers:

> "Hey [name], I'm [role] at [competing DEX]. We're launching our CLOB on Monad next month.
>
> I noticed you're running ~$330K on Kuru across MON/USDC and WETH/USDC, doing about 20K fills/day at a 4.7s refresh. Impressive volume.
>
> We'd like to offer you:
> - **0 maker fees** (Kuru charges 0 but we'll match)
> - **1 bps rebate** per fill (you earn from making, not just spread)
> - **Priority sequencing** (sub-100ms confirmation, beats your current 4.7s refresh window)
> - **$50K onboarding bonus** in our token (vested 3 months)
>
> At your current fill rate, the rebate alone = $200/day = $6K/month in pure additional income with no change to your strategy.
>
> Interested in a call?"

**Why this works:** You're not guessing. You KNOW their exact numbers. The offer is tailored to their specific situation. They can't get this from Kuru (who doesn't even know you're watching).

---

## Phase 4: Revenue Model

### Immediate Revenue (Month 1-3)

If you poach Maker 3 ($330K capital):
- Your DEX gains ~$330K in active liquidity
- Their fills attract takers (volume begets volume)
- Conservative: $500K/day facilitated volume
- At 2 bps taker fee: **$100/day = $3,000/month protocol revenue**

If you poach all 3 makers ($418K combined):
- ~$1-2M/day facilitated volume
- At 2 bps: **$200-400/day = $6-12K/month**

### Compounding Revenue (Month 3-12)

The real money isn't the direct fee revenue. It's the **flywheel:**

1. Poached makers → your DEX has liquidity
2. Liquidity → takers come (traders go where the spreads are tight)
3. Takers → more fill revenue for makers (they stay)
4. Volume → you can raise a Series A / attract more LPs
5. Series A → you deploy incentives → more makers come
6. Kuru loses makers → their spreads widen → more takers leave for you

**The flywheel math:**
- Kuru has $3.6M/day MON/USDC volume
- If you capture 30% of that by having tighter liquidity: $1.08M/day
- At 2 bps fee: **$216/day = $6,480/month just from MON/USDC**
- Across all pairs (Kuru does ~$5M+ total): **$10-15K/month**

Within 6 months, with continued intel + poaching:
- 50% market share of Monad orderbook volume: ~$16M/day
- At 2 bps: **$3,200/day = $96K/month**

---

## Phase 5: Ongoing Intelligence Value

The feed isn't just for the initial poach. Ongoing value:

**1. Counter-strategy in real-time**
- You see when Kuru's makers widen their spread (market stress) → you tighten yours to capture flow
- You see when they lose a maker (address goes quiet) → you announce publicly "we have X% more liquidity than competitors"

**2. Defense**
- If Kuru tries to poach YOUR makers, you'll see the new address appear on their feed and know immediately

**3. Pricing intelligence**
- Adjust your fee tiers based on actual maker behavior, not guesses
- If maker fill rates drop, reduce fees preemptively before they leave

**4. Investor pitch material**
- "Our intelligence shows competitor has only 3 active makers totaling $418K. We already have 5 makers with $800K. Here's the data."
- VCs eat this up. It's the kind of competitive moat evidence that gets you funded.

---

## Total P&L Estimate

| Timeframe | Revenue | Cost (feed + rebates) | Net |
|-----------|---------|----------------------|-----|
| Month 1-3 | $3-12K/month (fees) | $10K/month (feed) + $50K one-time (bonus) | -$47K to -$20K |
| Month 4-6 | $15-30K/month | $10K/month | +$5-20K/month |
| Month 7-12 | $50-96K/month | $10K/month | +$40-86K/month |
| **Year 1 total** | **~$400-700K** | **~$170K** | **+$230-530K** |

**ROI on the intelligence feed alone: 23-53x over 12 months.**

The $10K/month for the feed is the cheapest customer acquisition cost in DeFi. Traditional DEX marketing (token incentives, liquidity mining) costs $100K-$1M/month for uncertain results. This is surgical precision for $10K.

---

## The Most Aggressive Path: Full Information Warfare

If the buyer goes maximum aggression:

1. **Buy the feed** ($10K/month)
2. **Launch a "Kuru Maker Report"** — publicly post (anonymized) data showing Kuru's liquidity is concentrated in 3 makers. Frame it as "centralization risk." This scares retail users away from Kuru.
3. **Time your launch** to coincide with a moment when the feed shows Kuru's makers are pulling back (balance drops, order rate slows). Launch your DEX when Kuru looks weakest.
4. **Offer migration tool** — one-click move from Kuru margin to your protocol. Reduce friction to zero.
5. **Run the feed PUBLICLY** — show traders "look at this maker's real-time activity on Kuru, completely exposed, no privacy." Users lose confidence in Kuru's security → migrate to you.

That last one is the nuclear option. Publishing the vulnerability publicly — not exploiting it, just showing it exists — causes reputational damage that costs Kuru months of trust-building.

---

## Why This Is Real (Not Theoretical)

- **SushiSwap did this to Uniswap** in 2020 — $1.14B drained in a single week
- **Hyperliquid recently lost $60M** to a coordinated vampire attack (19 wallets, planned for weeks)
- **Kraken, Gemini, and Kalshi** all run maker rebate programs specifically to prevent this — they know the threat

The difference here: those attacks were BLIND. They didn't know who specifically to target. With this feed, you know names, amounts, strategies, and timing. It's a guided missile versus a carpet bomb.

---

## Summary for your team:

A competing DEX buying this $10K/month feed can realistically:
- Poach $330K+ in maker capital in weeks (not months)
- Build $50-96K/month in protocol revenue within 6-12 months
- Achieve 23-53x ROI on the intelligence investment
- Permanently damage Kuru's competitive position on Monad

All because the WebSocket `user` channel has no authentication.
