"""Stage 4a: capacity-tiered benchmarks (Phase 1 classes) vs a single benchmark with the SAME total allowances.
Toy fleet, illustrative only. Benchmark values must be verified against Permen ESDM 16/2022 before citing."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 1. Same toy fleet as stages 1-3 ---
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

# --- 2. NEW: plant class -> benchmark (Phase 1 values from the ESDM announcement; VERIFY against the regulation) ---
BENCHMARK_BY_CLASS = {
    "coal_25_to_100MW": 1.297,         # not used by this toy fleet (all plants >= 200 MW)
    "mine_mouth_100MW_plus": 1.089,
    "non_mine_mouth_100_to_400MW": 1.011,
    "non_mine_mouth_over_400MW": 0.911,
}
# Mine-mouth status is NOT in our toy data: assume ~25% of plants (a third generator, so nothing above changes)
rng3 = np.random.default_rng(11)
fleet["mine_mouth"] = rng3.random(n) < 0.25

def plant_class(row):
    if row.capacity_mw < 100:
        return "coal_25_to_100MW"
    if row.mine_mouth:
        return "mine_mouth_100MW_plus"
    return "non_mine_mouth_100_to_400MW" if row.capacity_mw <= 400 else "non_mine_mouth_over_400MW"

fleet["class"] = fleet.apply(plant_class, axis=1)
fleet["benchmark_tiered"] = fleet["class"].map(BENCHMARK_BY_CLASS)

# --- 3. Abatement assumptions: identical to stage 3 ---
rng2 = np.random.default_rng(7)
MAX_ABATE_SHARE = 0.30
fleet["mac_at_max"] = rng2.uniform(20, 80, n).round(1)
fleet["max_abate_tco2"] = fleet.emissions_tco2 * MAX_ABATE_SHARE
fleet["slope"] = fleet.mac_at_max / fleet.max_abate_tco2

def abatement_at_price(price):
    return np.minimum(price / fleet.slope, fleet.max_abate_tco2)

def abatement_cost(a):
    return 0.5 * fleet.slope * a**2

def solve(allowance):
    """Find the price at which fleet abatement equals (emissions - allowances)."""
    required = max(0.0, fleet.emissions_tco2.sum() - allowance.sum())
    lo, hi = 0.0, fleet.mac_at_max.max()
    for _ in range(100):
        mid = (lo + hi) / 2
        if abatement_at_price(mid).sum() < required:
            lo = mid
        else:
            hi = mid
    price = (lo + hi) / 2
    return price, abatement_at_price(price), required

# --- 4. Scenario A: tiered benchmarks.  Scenario B: ONE benchmark giving the same total allowances ---
allow_tiered = fleet.generation_mwh * fleet.benchmark_tiered
single_bm = allow_tiered.sum() / fleet.generation_mwh.sum()
allow_single = fleet.generation_mwh * single_bm

P_t, a_t, req_t = solve(allow_tiered)
P_s, a_s, req_s = solve(allow_single)

fleet["allow_tiered"] = allow_tiered
fleet["allow_single"] = allow_single
fleet["abatement"] = a_t
fleet["trade_tiered"] = fleet.emissions_tco2 - a_t - allow_tiered
fleet["trade_single"] = fleet.emissions_tco2 - a_s - allow_single
fleet["cost_tiered"] = abatement_cost(a_t) + fleet.trade_tiered * P_t
fleet["cost_single"] = abatement_cost(a_s) + fleet.trade_single * P_s
fleet["cost_change"] = fleet.cost_tiered - fleet.cost_single      # +ve = plant pays MORE under tiering

print("Class counts in the toy fleet:")
print(fleet["class"].value_counts().to_string())
print(f"\nEquivalent single benchmark (same total allowances): {single_bm:.3f} tCO2/MWh")
print(f"Required fleet abatement: tiered {req_t/1e6:.3f} Mt | single {req_s/1e6:.3f} Mt")
print(f"Clearing price:           tiered ${P_t:.2f}    | single ${P_s:.2f}")
print(f"Max difference in any plant's abatement between scenarios: {np.abs(a_t - a_s).max():.4f} t")

show = fleet[["plant", "capacity_mw", "class", "benchmark_tiered", "cost_tiered", "cost_single", "cost_change"]].copy()
show["cost_tiered"] = (show.cost_tiered / 1e6).round(2)
show["cost_single"] = (show.cost_single / 1e6).round(2)
show["cost_change"] = (show.cost_change / 1e6).round(2)
print("\nCosts in USD million (toy values):")
print(show.to_string(index=False))

by_class = fleet.groupby("class").agg(plants=("plant", "count"),
                                      cost_change_musd=("cost_change", lambda s: s.sum() / 1e6))
print("\nNet cost change from tiering, by class (USD million; + = pays more):")
print(by_class.round(2).to_string())
print(f"Sum across fleet (should be ~0): {fleet.cost_change.sum()/1e6:.4f}")

# --- 5. Chart (saved straight into figures/, which is committed to GitHub) ---
os.makedirs("figures", exist_ok=True)
colors = {"mine_mouth_100MW_plus": "tab:orange", "non_mine_mouth_100_to_400MW": "tab:blue",
          "non_mine_mouth_over_400MW": "tab:green", "coal_25_to_100MW": "tab:gray"}
o = fleet.sort_values("cost_change")
plt.figure(figsize=(9, 4.5))
plt.bar(o.plant, o.cost_change / 1e6, color=[colors[c] for c in o["class"]])
plt.axhline(0, color="black", linewidth=0.8)
plt.xticks(rotation=60, ha="right")
plt.ylabel("Cost change vs single benchmark (USD million)")
plt.title("Who gains and loses from tiered benchmarks (same total allowances)")
handles = [plt.Rectangle((0, 0), 1, 1, color=colors[c]) for c in colors if c in set(fleet["class"])]
plt.legend(handles, [c for c in colors if c in set(fleet["class"])], fontsize=8)
plt.tight_layout()
plt.savefig("figures/stage4a.png", dpi=150)
