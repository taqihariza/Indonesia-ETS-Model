"""
Stage 4b, fixed price: what does the four-tier benchmark cost each tier at the LEGAL carbon price?

Run from the repo root:   python src/ets_stage4b_price.py
(needs src/ets_stage4b.py, which it re-uses)

Why a fixed price
  No PTBAE-PU allowance has traded yet, so there is no observed ETS price.
  The only government-defined price is the carbon tax in Law No. 7/2021:
  Rp30,000 per tonne CO2e, about $2 (not yet in force; used here as a REFERENCE price).
  So instead of letting the price come out of my assumed abatement costs,
  I set the price by hand and ask: what does each tier pay or gain?

What the model does
  Cost change for a unit = price x (allowances under single benchmark - allowances under four tiers)
  It does not depend on abatement costs. Only capacity factor (generation) matters,
  so the Monte Carlo redraws capacity factor only.
"""
import numpy as np
import pandas as pd

import ets_stage4b as m   # re-use fleet, tiers and settings from Stage 4b

CARBON_TAX_USD = 2.0                     # Rp30,000/t at roughly Rp15,000 per USD
PRICES = [CARBON_TAX_USD, 4.5, 10.0, 18.0]   # reference price first, then sensitivity


def allowance_gap(fleet, cf):
    """Per-unit (single-benchmark allowances - four-tier allowances), in tCO2.
    Positive = the unit gets FEWER allowances under four tiers, so it pays more."""
    gen = fleet["capacity_mw"].to_numpy() * cf * m.HOURS
    allow_tier = gen * fleet["benchmark"].to_numpy()
    single_bm = allow_tier.sum() / gen.sum()
    return gen * single_bm - allow_tier


if __name__ == "__main__":
    fleet = m.load_fleet()
    n = len(fleet)

    # Base case: every unit at capacity factor 0.64
    gap0 = m.by_tier(fleet, allowance_gap(fleet, np.full(n, m.BASE_CF)))   # tCO2 per tier

    print("=" * 70)
    print(f"FIXED PRICE: carbon tax reference ${CARBON_TAX_USD:.2f}/t (Rp30,000/t, Law 7/2021)")
    print("=" * 70)
    print("Allowances a tier loses (+) or gains (-) under four tiers vs single benchmark")
    print("(base case, capacity factor 0.64):")
    print((gap0 / 1e6).round(2).rename("Mt CO2").to_string(), "\n")

    base = pd.DataFrame({f"${p:g}/t": gap0 * p / 1e6 for p in PRICES}).round(1)
    print("Base case: change in net cost, four-tier vs single ($M per year)")
    print("Positive = pays MORE under four tiers.")
    print(base.to_string(), "\n")

    # Monte Carlo over capacity factor only (same seed and range as Stage 4b)
    rng = np.random.default_rng(m.SEED)
    gaps = []
    for _ in range(m.N_RUNS):
        cf = rng.uniform(*m.CF_RANGE, n)
        gaps.append(m.by_tier(fleet, allowance_gap(fleet, cf)).to_numpy())
    gaps = pd.DataFrame(gaps, columns=m.TIERS) / 1e6        # Mt per run

    print(f"Monte Carlo ({m.N_RUNS} runs, capacity factor redrawn): "
          f"median / 5th / 95th pct, $M per year")
    for p in PRICES:
        c = gaps * p
        out = pd.DataFrame({
            "median": c.median(), "5th pct": c.quantile(.05), "95th pct": c.quantile(.95),
            "share of runs paying more": (c > 0).mean(),
        }).round(2)
        tag = "  <- legal carbon tax reference" if p == CARBON_TAX_USD else ""
        print(f"\nPrice ${p:g}/t{tag}")
        print(out.to_string())
