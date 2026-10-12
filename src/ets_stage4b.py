"""
Stage 4b: four-tier benchmark vs single benchmark on the REAL Indonesian coal fleet.

Run from the repo root:   python src/ets_stage4b.py

What is real and what is assumed
  REAL (GEM, July 2026):   which units exist, capacity (MW), mine-mouth flag,
                           heat rate and emission factor (GEM estimates).
  ASSUMED (by me):         capacity factor (GEM only gives a flat 0.64),
                           abatement costs (not public), abatement potential.
  Both assumed things are drawn at random in the Monte Carlo.

Data: Global Energy Monitor, Global Coal Plant Tracker, July 2026 (CC BY 4.0).
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # draw to a file, no window needed
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "gem_indonesia_operating_noncaptive.csv"
OUT_CSV = ROOT / "outputs" / "stage4b_montecarlo.csv"
OUT_FIG = ROOT / "figures" / "stage4b.png"

# ---------------------------------------------------------------- settings
# Phase 1 benchmarks, tCO2e per MWh. NOT yet checked against Permen ESDM 16/2022.
BENCHMARK = {"small": 1.297, "mine_mouth": 1.089, "mid": 1.011, "large": 0.911}
TIERS = list(BENCHMARK)
HOURS = 8760

N_RUNS = 1000
SEED = 42
CF_RANGE = (0.50, 0.85)          # capacity factor: random per unit (assumption)
ABATE_FRAC_RANGE = (0.05, 0.25)  # max abatement as share of the unit's emissions (assumption)
COST_AT_MAX_RANGE = (20, 100)    # USD/tCO2 marginal cost at max abatement (assumption)

# Base case (single deterministic run) uses the middle of these ranges for everyone.
BASE_CF, BASE_ABATE_FRAC, BASE_COST_AT_MAX = 0.64, 0.15, 60.0


# ---------------------------------------------------------------- step 1: fleet
def load_fleet():
    df = pd.read_csv(DATA)

    # Tier rule: <100 MW is "small" (any type); from 100 MW up, mine-mouth is its own tier;
    # non-mine-mouth is "mid" for 100 <= MW <= 400 and "large" above 400 MW.
    mw, mm = df["capacity_mw"], df["minemouth"]
    df["tier"] = np.select(
        [mw < 100, mm, mw <= 400],
        ["small", "mine_mouth", "mid"],
        default="large",
    )
    df["benchmark"] = df["tier"].map(BENCHMARK)

    # Emission intensity (tCO2/MWh) = heat rate x emission factor, with unit conversion:
    #   Btu/kWh -> TJ/MWh : x 1.05506e-6 ;  kg/TJ -> t : /1000
    df["intensity"] = (
        df["heat_rate_btu_per_kwh"] * 1.05506e-6 * df["emission_factor_kg_per_tj"] / 1000
    )
    return df


# ---------------------------------------------------------------- step 2: market
def clear_market(position, a_max, cost_at_max):
    """Find the carbon price where total abatement = total shortfall (bisection).

    Each unit has a straight-line marginal abatement cost (MAC):
        MAC_i(a) = slope_i * a,  slope_i = cost_at_max_i / a_max_i,  a <= a_max_i
    At price p a unit abates a_i = min(p / slope_i, a_max_i).
    Market clears when sum(a_i) = sum(position_i)  (position = emissions - allowances).
    Returns (price, abatement per unit, infeasible flag).
    """
    slope = cost_at_max / a_max
    short = position.sum()
    if short <= 0:                       # cap does not bind: allowances are plentiful
        return 0.0, np.zeros_like(position), False

    def abatement(p):
        return np.minimum(p / slope, a_max)

    hi = cost_at_max.max()               # above this price every unit is at its limit
    if abatement(hi).sum() < short:      # even full abatement cannot close the gap
        return hi, abatement(hi), True

    lo = 0.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if abatement(mid).sum() < short:
            lo = mid
        else:
            hi = mid
    price = (lo + hi) / 2
    return price, abatement(price), False


def run_once(fleet, cf, abate_frac, cost_at_max):
    """One full run: same fleet, same costs, two allocation rules."""
    mw = fleet["capacity_mw"].to_numpy()
    gen = mw * cf * HOURS                                  # MWh per year (fixed, no output effects)
    emis = gen * fleet["intensity"].to_numpy()             # tCO2 per year
    allow_tier = gen * fleet["benchmark"].to_numpy()       # four-tier allowances
    # Single benchmark: ONE number that gives the same total allowances.
    single_bm = allow_tier.sum() / gen.sum()
    allow_single = gen * single_bm

    a_max = abate_frac * emis
    result = {}
    for name, allow in (("tier", allow_tier), ("single", allow_single)):
        position = emis - allow                            # >0 short (must buy), <0 long (can sell)
        price, a, infeasible = clear_market(position, a_max, cost_at_max)
        abate_cost = 0.5 * (cost_at_max / a_max) * a**2    # area under the straight-line MAC
        net_cost = abate_cost + price * (position - a)     # abatement + allowance purchases - sales
        result[name] = dict(position=position, price=price, abated=a,
                            net_cost=net_cost, infeasible=infeasible)
    result["single_bm"] = single_bm
    result["emis"] = emis
    return result


def by_tier(fleet, values):
    return pd.Series(values).groupby(fleet["tier"].to_numpy()).sum().reindex(TIERS)


# ---------------------------------------------------------------- step 3: base case
def base_case(fleet):
    n = len(fleet)
    r = run_once(fleet, np.full(n, BASE_CF), np.full(n, BASE_ABATE_FRAC),
                 np.full(n, BASE_COST_AT_MAX))
    pos = r["tier"]["position"]
    diff = r["tier"]["net_cost"] - r["single"]["net_cost"]

    table = pd.DataFrame({
        "units": fleet["tier"].value_counts().reindex(TIERS),
        "position_Mt (+short/-long)": by_tier(fleet, pos) / 1e6,
        "net_cost_change_vs_single_$M": by_tier(fleet, diff) / 1e6,
    }).round(2)
    table.loc["Total"] = table.sum()

    print("=" * 70)
    print(f"BASE CASE: every unit at capacity factor {BASE_CF}, identical abatement costs")
    print("=" * 70)
    print(f"Fleet emissions (model):        {r['emis'].sum() / 1e6:8.1f} Mt")
    print(f"Net shortfall, four-tier:       {pos.sum() / 1e6:8.2f} Mt "
          f"({100 * pos.sum() / r['emis'].sum():.1f}% of emissions)")
    print(f"Single benchmark that matches:  {r['single_bm']:8.3f} tCO2/MWh")
    print(f"Carbon price, four-tier:        {r['tier']['price']:8.2f} $/t")
    print(f"Carbon price, single benchmark: {r['single']['price']:8.2f} $/t")
    print(f"Abatement, four-tier / single:  {r['tier']['abated'].sum() / 1e6:.2f} / "
          f"{r['single']['abated'].sum() / 1e6:.2f} Mt\n")
    print(table.to_string(), "\n")
    print("Positive cost change = the tier pays MORE under the four-tier benchmark.\n")


# ---------------------------------------------------------------- step 4: Monte Carlo
def monte_carlo(fleet):
    rng = np.random.default_rng(SEED)
    n = len(fleet)
    rows = []
    for run in range(N_RUNS):
        cf = rng.uniform(*CF_RANGE, n)
        frac = rng.uniform(*ABATE_FRAC_RANGE, n)
        cost = rng.uniform(*COST_AT_MAX_RANGE, n)
        r = run_once(fleet, cf, frac, cost)

        # With fixed generation and equal total allowances, price must be the same.
        assert np.isclose(r["tier"]["price"], r["single"]["price"], atol=1e-6)

        diff = by_tier(fleet, r["tier"]["net_cost"] - r["single"]["net_cost"]) / 1e6
        pos = by_tier(fleet, r["tier"]["position"]) / 1e6
        row = {"run": run,
               "short_Mt": pos.sum(),
               "short_pct": 100 * pos.sum() * 1e6 / r["emis"].sum(),
               "price": r["tier"]["price"],
               "infeasible": r["tier"]["infeasible"]}
        row.update({f"cost_change_{t}_$M": diff[t] for t in TIERS})
        row.update({f"position_{t}_Mt": pos[t] for t in TIERS})
        rows.append(row)
    mc = pd.DataFrame(rows)
    OUT_CSV.parent.mkdir(exist_ok=True)
    mc.to_csv(OUT_CSV, index=False)
    return mc


def summarise(mc):
    binding = mc[mc["price"] > 0]
    print("=" * 70)
    print(f"MONTE CARLO: {N_RUNS} runs (seed {SEED}); capacity factor, abatement potential and")
    print("abatement cost redrawn every run; the fleet itself is fixed (real GEM units)")
    print("=" * 70)
    print(f"Runs where the cap binds (price > 0):   {len(binding)} of {N_RUNS} "
          f"({100 * len(binding) / N_RUNS:.1f}%)")
    print(f"Runs where abatement cannot close gap:  {int(mc['infeasible'].sum())}")
    print(f"Fleet shortfall, % of emissions:  median {mc['short_pct'].median():.1f}, "
          f"5th-95th pct {mc['short_pct'].quantile(.05):.1f} to {mc['short_pct'].quantile(.95):.1f}")
    if len(binding):
        print(f"Carbon price ($/t, binding runs): median {binding['price'].median():.1f}, "
              f"5th-95th pct {binding['price'].quantile(.05):.1f} to {binding['price'].quantile(.95):.1f}")
    print("\nNet cost change, four-tier vs single benchmark (binding runs, $M per year):")
    out = pd.DataFrame({
        t: {
            "share of runs paying more": (binding[f"cost_change_{t}_$M"] > 0).mean(),
            "median": binding[f"cost_change_{t}_$M"].median(),
            "5th pct": binding[f"cost_change_{t}_$M"].quantile(.05),
            "95th pct": binding[f"cost_change_{t}_$M"].quantile(.95),
        } for t in TIERS
    }).T.round(2)
    print(out.to_string(), "\n")


# ---------------------------------------------------------------- step 5: figure
def make_figure(mc):
    binding = mc[mc["price"] > 0]
    labels = ["Small\n<100 MW", "Mine-mouth\n>=100 MW", "Mid\n100-400 MW", "Large\n>400 MW"]
    data = [binding[f"cost_change_{t}_$M"] for t in TIERS]

    fig, ax = plt.subplots(figsize=(8, 5))
    bp = ax.boxplot(data, tick_labels=labels, widths=0.5, patch_artist=True, showfliers=False,
                    whis=(5, 95))
    for box in bp["boxes"]:
        box.set(facecolor="#9fb6cd", edgecolor="#3d5a80", linewidth=1.2)
    for m in bp["medians"]:
        m.set(color="#1b2a41", linewidth=2)
    ax.axhline(0, color="#555", linewidth=1)
    ax.set_ylabel("Change in net cost vs single benchmark ($M per year)\n"
                  "above zero = pays more under four tiers")
    ax.set_title("Who gains and who pays when benchmarks are tiered by plant size\n"
                 f"(real GEM fleet, {len(binding)} runs where the cap binds; whiskers 5th-95th pct)",
                 fontsize=11)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    OUT_FIG.parent.mkdir(exist_ok=True)
    fig.savefig(OUT_FIG, dpi=150)
    print(f"Saved {OUT_CSV.relative_to(ROOT)} and {OUT_FIG.relative_to(ROOT)}")


if __name__ == "__main__":
    fleet = load_fleet()
    print(f"Fleet: {len(fleet)} units, {fleet['capacity_mw'].sum():,.0f} MW\n")
    print(fleet["tier"].value_counts().reindex(TIERS).to_string(), "\n")
    base_case(fleet)
    mc = monte_carlo(fleet)
    summarise(mc)
    make_figure(mc)
