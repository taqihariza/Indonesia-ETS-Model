"""Stage 2: allowance allocation and compliance positions (toy fleet, illustrative only)."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# --- 1. Rebuild the same toy fleet as stage 1 (same seed, same order) ---
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

# --- 2. Policy parameters (change these to run scenarios) ---
BENCHMARK = 1.00      # tCO2/MWh: allowance granted per MWh generated (toy value)
PRICE = 10.0          # USD per tCO2 (toy value)

# --- 3. Allocation: intensity-based, allowances = generation x benchmark ---
fleet["allowance_tco2"] = fleet.generation_mwh * BENCHMARK

# --- 4. Compliance position: positive = short (must buy), negative = long (can sell) ---
fleet["position_tco2"] = fleet.emissions_tco2 - fleet.allowance_tco2
fleet["cost_usd"] = fleet.position_tco2 * PRICE   # negative = revenue from selling

short = fleet.position_tco2.clip(lower=0).sum()
long_ = (-fleet.position_tco2).clip(lower=0).sum()

print(fleet[["plant", "intensity_tco2_mwh", "emissions_tco2",
             "allowance_tco2", "position_tco2", "cost_usd"]].round(0).to_string(index=False))
print(f"\nBenchmark: {BENCHMARK} tCO2/MWh | Price: ${PRICE}/tCO2")
print(f"Total emissions:   {fleet.emissions_tco2.sum()/1e6:6.2f} Mt")
print(f"Total allowances:  {fleet.allowance_tco2.sum()/1e6:6.2f} Mt")
print(f"Short (need to buy): {short/1e6:6.2f} Mt")
print(f"Long (can sell):     {long_/1e6:6.2f} Mt")
print(f"Net fleet position:  {(short-long_)/1e6:6.2f} Mt  (positive = fleet is short overall)")
print(f"Net compliance cost: ${fleet.cost_usd.sum()/1e6:,.1f} million")

# --- 5. Chart: who buys and who sells ---
ordered = fleet.sort_values("position_tco2")
colors = ["tab:green" if p < 0 else "tab:red" for p in ordered.position_tco2]
plt.figure(figsize=(9, 4))
plt.bar(ordered.plant, ordered.position_tco2 / 1e6, color=colors)
plt.axhline(0, color="black", linewidth=0.8)
plt.xticks(rotation=60, ha="right")
plt.ylabel("Position (MtCO2)")
plt.title(f"Compliance position by plant (benchmark {BENCHMARK} tCO2/MWh)")
plt.tight_layout()
plt.savefig("outputs/positions.png", dpi=150)
