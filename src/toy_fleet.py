"""Stage 1: a fictional fleet of 15 coal plants (illustrative numbers only)."""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

rng = np.random.default_rng(42)   # fixed seed = same results every run
n = 15

fleet = pd.DataFrame({
    "plant": [f"Plant_{i+1:02d}" for i in range(n)],
    "capacity_mw": rng.integers(200, 1000, n),
    "capacity_factor": rng.uniform(0.55, 0.85, n).round(2),
    "intensity_tco2_mwh": rng.uniform(0.85, 1.25, n).round(3),
})

# generation = capacity x capacity factor x hours in a year
fleet["generation_mwh"] = fleet.capacity_mw * fleet.capacity_factor * 8760
# emissions = generation x emissions intensity
fleet["emissions_tco2"] = fleet.generation_mwh * fleet.intensity_tco2_mwh

print(fleet.round(2).to_string(index=False))
print(f"\nFleet emissions: {fleet.emissions_tco2.sum() / 1e6:.1f} MtCO2")
print(f"Fleet average intensity: "
      f"{fleet.emissions_tco2.sum() / fleet.generation_mwh.sum():.3f} tCO2/MWh")

ordered = fleet.sort_values("intensity_tco2_mwh")
plt.figure(figsize=(9, 4))
plt.bar(ordered.plant, ordered.intensity_tco2_mwh)
plt.xticks(rotation=60, ha="right")
plt.ylabel("tCO2 per MWh")
plt.title("Toy fleet: emissions intensity by plant")
plt.tight_layout()
plt.savefig("outputs/fleet_intensity.png", dpi=150)
