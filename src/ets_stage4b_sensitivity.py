"""
Stage 4b sensitivity: does the result survive different scope and classification choices?

Run from the repo root:   python src/ets_stage4b_sensitivity.py
(needs src/ets_stage4b.py, which it re-uses)

Scenarios
  1. base            All 147 units, four tiers (the Stage 4b setup).
  2. only_100mw_up   Only the 112 units of 100 MW or more (drops the small tier).
  3. no_minemouth    Ignore the mine-mouth flag: those units are put in tiers by size only.
                     Why: GEM flags 22 units of 100 MW or more as mine-mouth, but ESDM
                     reported only 14 mine-mouth units in Phase 1, so the flag may differ.

Same random assumptions as Stage 4b (capacity factor, abatement potential and cost).
"""
import numpy as np
import pandas as pd

import ets_stage4b as m   # re-use the model from Stage 4b


def make_fleet(base, scenario):
    f = base.copy()
    if scenario == "only_100mw_up":
        f = f[f["capacity_mw"] >= 100].reset_index(drop=True)
    elif scenario == "no_minemouth":
        mw = f["capacity_mw"]
        f["tier"] = np.select([mw < 100, mw <= 400], ["small", "mid"], default="large")
        f["benchmark"] = f["tier"].map(m.BENCHMARK)
    return f


def run_scenario(fleet):
    tiers = [t for t in m.TIERS if (fleet["tier"] == t).any()]
    rng = np.random.default_rng(m.SEED)
    n = len(fleet)

    # Base case: every unit at capacity factor 0.64, identical abatement costs.
    r0 = m.run_once(fleet, np.full(n, m.BASE_CF), np.full(n, m.BASE_ABATE_FRAC),
                    np.full(n, m.BASE_COST_AT_MAX))
    base = {
        "units": n,
        "MW": fleet["capacity_mw"].sum(),
        "short_pct": 100 * r0["tier"]["position"].sum() / r0["emis"].sum(),
        "price": r0["tier"]["price"],
        "single_bm": r0["single_bm"],
    }
    base_diff = m.by_tier(fleet, r0["tier"]["net_cost"] - r0["single"]["net_cost"]) / 1e6

    # Monte Carlo: same ranges as Stage 4b.
    diffs, prices = [], []
    for _ in range(m.N_RUNS):
        cf = rng.uniform(*m.CF_RANGE, n)
        frac = rng.uniform(*m.ABATE_FRAC_RANGE, n)
        cost = rng.uniform(*m.COST_AT_MAX_RANGE, n)
        r = m.run_once(fleet, cf, frac, cost)
        diffs.append(m.by_tier(fleet, r["tier"]["net_cost"] - r["single"]["net_cost"]) / 1e6)
        prices.append(r["tier"]["price"])
    mc = pd.DataFrame(diffs)[tiers]
    prices = np.array(prices)
    binding = prices > 0
    return tiers, base, base_diff, mc[binding], prices


if __name__ == "__main__":
    fleet0 = m.load_fleet()
    labels = {
        "base": "1. Base: all 147 units",
        "only_100mw_up": "2. Only units of 100 MW or more",
        "no_minemouth": "3. Ignore the mine-mouth flag",
    }
    for key, label in labels.items():
        fleet = make_fleet(fleet0, key)
        tiers, base, base_diff, mc, prices = run_scenario(fleet)

        print("=" * 72)
        print(label)
        print("=" * 72)
        print(f"Units: {base['units']}   Capacity: {base['MW']:,.0f} MW")
        print(f"Base case: shortfall {base['short_pct']:.1f}% of emissions, "
              f"price ${base['price']:.2f}/t, single benchmark {base['single_bm']:.3f} tCO2/MWh")
        print(f"Monte Carlo ({m.N_RUNS} runs): cap binds in {100 * (prices > 0).mean():.1f}% of runs")
        out = pd.DataFrame({
            t: {
                "units": int((fleet["tier"] == t).sum()),
                "base case $M": base_diff[t],
                "MC median $M": mc[t].median(),
                "MC 5th pct": mc[t].quantile(.05),
                "MC 95th pct": mc[t].quantile(.95),
                "share of runs paying more": (mc[t] > 0).mean(),
            } for t in tiers
        }).T.round(2)
        print("Net cost change, four-tier vs single benchmark ($M per year):")
        print(out.to_string(), "\n")
