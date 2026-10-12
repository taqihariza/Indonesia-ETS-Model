"""Stage 3: abatement costs, trading and the market-clearing carbon price (toy fleet, illustrative only)."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 1. Same toy fleet as stages 1-2 (seed 42, same order of draws) ---
rng = np.random.default_rng(42)
n = 15
fleet = pd.DataFrame({
    "plant": [f"Plant_{i+1:02d}" for i in range(n)],
    "capacity_mw": rng.integers(200, 1000, n),
    "capacity_factor": rng.uniform(0.55, 0.85, n).round(2),
    "intensity_tco2_mwh": rng.uniform(0.85, 1.25, n).round(3),
})
fleet["generation_mwh"] = fleet.capacity_mw * fleet.capacity_factor * 8760
fleet["emissions_tco2"] = fleet.generation_mwh * fleet.intensity_tco2_mwh

# --- 2. Abatement assumptions (toy values; a SECOND generator so the fleet above is unchanged) ---
rng2 = np.random.default_rng(7)
MAX_ABATE_SHARE = 0.30   # a plant can cut at most 30% of its emissions
# marginal abatement cost (USD/tCO2) at the plant's maximum abatement; rises linearly from 0
fleet["mac_at_max"] = rng2.uniform(20, 80, n).round(1)
fleet["max_abate_tco2"] = fleet.emissions_tco2 * MAX_ABATE_SHARE
# MAC_i(a) = slope_i * a   =>   slope_i = mac_at_max / max_abate
fleet["slope"] = fleet.mac_at_max / fleet.max_abate_tco2

def abatement_at_price(price):
    """Each plant abates until its marginal cost equals the price (capped at its maximum)."""
    return np.minimum(price / fleet.slope, fleet.max_abate_tco2)

def abatement_cost(a):
    """Total cost of abating a tonnes = area under a linear MAC curve = 0.5 * slope * a^2."""
    return 0.5 * fleet.slope * a**2

def solve(benchmark):
    allowance = fleet.generation_mwh * benchmark
    required = max(0.0, fleet.emissions_tco2.sum() - allowance.sum())   # fleet-wide abatement needed
    if required == 0:
        return dict(benchmark=benchmark, required=0, price=0.0, feasible=True, a=abatement_at_price(0.0), allowance=allowance)
    if required > fleet.max_abate_tco2.sum():
        return dict(benchmark=benchmark, required=required, price=np.nan, feasible=False, a=None, allowance=allowance)
    lo, hi = 0.0, fleet.mac_at_max.max()
    for _ in range(100):                      # bisection: find price where total abatement = required
        mid = (lo + hi) / 2
        if abatement_at_price(mid).sum() < required:
            lo = mid
        else:
            hi = mid
    return dict(benchmark=benchmark, required=required, price=(lo + hi) / 2, feasible=True,
                a=abatement_at_price((lo + hi) / 2), allowance=allowance)

# --- 3. Detailed run at one benchmark ---
BENCHMARK = 0.95
res = solve(BENCHMARK)
P = res["price"]
fleet["allowance_tco2"] = res["allowance"]
fleet["abatement_tco2"] = res["a"]
fleet["emissions_after"] = fleet.emissions_tco2 - fleet.abatement_tco2
fleet["trade_tco2"] = fleet.emissions_after - fleet.allowance_tco2          # +ve = buys, -ve = sells
fleet["abate_cost_usd"] = abatement_cost(fleet.abatement_tco2)
fleet["allowance_cost_usd"] = fleet.trade_tco2 * P                           # -ve = revenue
fleet["total_cost_usd"] = fleet.abate_cost_usd + fleet.allowance_cost_usd

print(f"Benchmark {BENCHMARK} tCO2/MWh")
print(f"Required fleet abatement: {res['required']/1e6:.2f} Mt   |   Clearing price: ${P:.2f}/tCO2\n")
show = fleet[["plant", "mac_at_max", "abatement_tco2", "trade_tco2", "total_cost_usd"]].copy()
print(show.round(0).to_string(index=False))
print(f"\nCheck: total abatement   = {fleet.abatement_tco2.sum()/1e6:.3f} Mt")
print(f"Check: net trades (should be ~0) = {fleet.trade_tco2.sum():.1f} t")
cost_trading = fleet.abate_cost_usd.sum()
print(f"Fleet abatement cost WITH trading: ${cost_trading/1e6:,.1f} million")

# --- 4. Counterfactual: same total abatement, but every plant cuts the SAME percentage (no price signal) ---
uniform_share = res["required"] / fleet.emissions_tco2.sum()
a_uniform = fleet.emissions_tco2 * uniform_share
assert (a_uniform <= fleet.max_abate_tco2).all(), "uniform cut exceeds some plant's maximum"
cost_uniform = abatement_cost(a_uniform).sum()
print(f"Uniform-cut alternative (every plant cuts {uniform_share*100:.1f}%, same {a_uniform.sum()/1e6:.3f} Mt in total):")
print(f"Fleet abatement cost, uniform cut:  ${cost_uniform/1e6:,.1f} million")
print(f"Fleet abatement cost, with trading: ${cost_trading/1e6:,.1f} million")
print(f"Saving from letting the market decide who abates: ${(cost_uniform-cost_trading)/1e6:,.1f} million "
      f"({(1-cost_trading/cost_uniform)*100:.0f}%)")

# --- 5. Scenario sweep: how does the price respond to tighter benchmarks? ---
print("\nBenchmark sweep")
rows = []
for b in [1.00, 0.98, 0.96, 0.94, 0.92, 0.90, 0.88, 0.86, 0.84]:
    r = solve(b)
    rows.append((b, r["required"]/1e6, r["price"], r["feasible"]))
sweep = pd.DataFrame(rows, columns=["benchmark", "required_Mt", "price_usd_t", "feasible"])
print(sweep.round(2).to_string(index=False))

# --- 6. Charts ---
fig, ax = plt.subplots(1, 2, figsize=(11, 4))
ok = sweep[sweep.feasible]
ax[0].plot(ok.benchmark, ok.price_usd_t, marker="o")
ax[0].invert_xaxis()
ax[0].set_xlabel("Benchmark (tCO2/MWh), tighter to the right")
ax[0].set_ylabel("Clearing price (USD/tCO2)")
ax[0].set_title("Carbon price vs benchmark stringency")
o = fleet.sort_values("abatement_tco2")
ax[1].bar(o.plant, o.abatement_tco2 / 1e6)
ax[1].set_xticks(range(len(o)))
ax[1].set_xticklabels(o.plant, rotation=60, ha="right")
ax[1].set_ylabel("Abatement (MtCO2)")
ax[1].set_title(f"Who abates at benchmark {BENCHMARK} (price ${P:.1f})")
plt.tight_layout()
plt.savefig("outputs/stage3.png", dpi=150)
