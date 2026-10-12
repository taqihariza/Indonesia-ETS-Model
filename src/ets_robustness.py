"""Robustness: is the 'tiered vs single benchmark' result stable across many random synthetic fleets?
Everything here is synthetic; benchmark values from the ESDM announcement / ICAP (verify against Permen ESDM 16/2022)."""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

BENCH = {"mine_mouth": 1.089, "mid": 1.011, "large": 0.911}   # 25-100 MW class never occurs: capacities drawn from 200-1000 MW
CLASSES = ["mine_mouth", "mid", "large"]
N_PLANTS = 15
MAX_ABATE_SHARE = 0.30

def draw_fleet(rng, p_mine_mouth):
    cap = rng.integers(200, 1000, N_PLANTS)
    cf = rng.uniform(0.55, 0.85, N_PLANTS)
    intensity = rng.uniform(0.85, 1.25, N_PLANTS)
    gen = cap * cf * 8760
    emis = gen * intensity
    mine = rng.random(N_PLANTS) < p_mine_mouth
    cls = np.where(mine, "mine_mouth", np.where(cap <= 400, "mid", "large"))
    mac_max = rng.uniform(20, 80, N_PLANTS)
    max_ab = MAX_ABATE_SHARE * emis
    return dict(gen=gen, emis=emis, cls=cls, mac_max=mac_max, max_ab=max_ab, slope=mac_max / max_ab)

def solve(f, allowance):
    """Return (price, abatement) or None if the cap cannot be met."""
    required = f["emis"].sum() - allowance.sum()
    if required <= 0:
        return 0.0, np.zeros(N_PLANTS)
    if required > f["max_ab"].sum():
        return None
    lo, hi = 0.0, f["mac_max"].max()
    for _ in range(60):
        mid = (lo + hi) / 2
        if np.minimum(mid / f["slope"], f["max_ab"]).sum() < required:
            lo = mid
        else:
            hi = mid
    p = (lo + hi) / 2
    return p, np.minimum(p / f["slope"], f["max_ab"])

def run_once(rng, p_mm):
    f = draw_fleet(rng, p_mm)
    bm = np.array([BENCH[c] for c in f["cls"]])
    allow_t = f["gen"] * bm
    allow_s = f["gen"] * (allow_t.sum() / f["gen"].sum())     # single benchmark with the SAME total allowances
    rt, rs = solve(f, allow_t), solve(f, allow_s)
    if rt is None or rs is None:
        return None
    (P_t, a_t), (P_s, a_s) = rt, rs
    cost = lambda a: 0.5 * f["slope"] * a**2
    cost_t = cost(a_t) + (f["emis"] - a_t - allow_t) * P_t
    cost_s = cost(a_s) + (f["emis"] - a_s - allow_s) * P_s
    change = cost_t - cost_s
    out = {"price": P_t, "price_gap": abs(P_t - P_s),
           "abate_gap": np.abs(a_t - a_s).max(), "net_zero_gap": abs(change.sum())}
    for c in CLASSES:
        m = f["cls"] == c
        out[c] = change[m].sum() / 1e6 if m.any() else np.nan     # USD million; NaN if class absent in this fleet
    return out

def simulate(n_runs, p_mm, seed):
    rng = np.random.default_rng(seed)
    rows, skipped = [], 0
    while len(rows) < n_runs:
        r = run_once(rng, p_mm)
        if r is None:
            skipped += 1
            continue
        rows.append(r)
    return pd.DataFrame(rows), skipped

# --- Main run: 1,000 fleets, 25% mine-mouth ---
main, skipped = simulate(1000, 0.25, seed=2026)
print(f"Main run: {len(main)} random fleets (skipped {skipped} where the cap could not be met)\n")
print("Invariants (should hold in EVERY run):")
print(f"  largest price gap, tiered vs single:        {main.price_gap.max():.2e} USD/t")
print(f"  largest single-plant abatement gap:         {main.abate_gap.max():.2e} t")
print(f"  largest |sum of cost changes| across fleet: {main.net_zero_gap.max():.2e} USD")
print(f"\nClearing price across fleets: median ${main.price.median():.2f}, 5th-95th pct ${main.price.quantile(.05):.2f} - ${main.price.quantile(.95):.2f}")

print("\nNet cost change from tiering by class, USD million (+ = class pays more):")
tab = pd.DataFrame({
    "runs_with_class": [main[c].notna().sum() for c in CLASSES],
    "median": [main[c].median() for c in CLASSES],
    "p5": [main[c].quantile(.05) for c in CLASSES],
    "p95": [main[c].quantile(.95) for c in CLASSES],
    "pct_runs_pays_more": [(main[c].dropna() > 0).mean() * 100 for c in CLASSES],
}, index=CLASSES)
print(tab.round(2).to_string())

# --- Sensitivity to the assumed mine-mouth share (my assumption, not data) ---
print("\nSensitivity to the assumed share of mine-mouth plants (500 fleets each):")
rows = []
for share in [0.10, 0.25, 0.40]:
    d, _ = simulate(500, share, seed=7)
    rows.append({"mine_mouth_share": share,
                 "median_mine_mouth": d.mine_mouth.median(),
                 "median_mid": d.mid.median(),
                 "median_large": d.large.median(),
                 "pct_large_pays_more": (d.large.dropna() > 0).mean() * 100})
print(pd.DataFrame(rows).round(2).to_string(index=False))

# --- Chart ---
os.makedirs("figures", exist_ok=True)
plt.figure(figsize=(7, 4.5))
plt.boxplot([main[c].dropna() for c in CLASSES], showfliers=False)
plt.xticks([1, 2, 3], ["mine-mouth\n(1.089)", "non-mine-mouth\n100-400 MW (1.011)", "non-mine-mouth\n>400 MW (0.911)"])
plt.axhline(0, color="black", linewidth=0.8)
plt.ylabel("Net cost change from tiering (USD million)")
plt.title("Transfer from tiering across 1,000 random synthetic fleets")
plt.tight_layout()
plt.savefig("figures/robustness.png", dpi=150)
