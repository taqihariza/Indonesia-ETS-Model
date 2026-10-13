"""
Figure for the fixed-price run: who pays and who gains at the legal carbon tax ($2/t).

Run from the repo root:   python src/ets_stage4b_price_figure.py
Writes figures/stage4b_price.png. Re-uses src/ets_stage4b_price.py and src/ets_stage4b.py.
Bars = Monte Carlo median over 1000 capacity-factor draws; whiskers = 5th-95th percentile.
"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

import ets_stage4b as m
from ets_stage4b_price import CARBON_TAX_USD, allowance_gap

PAY_MORE, PAY_LESS = "#d03b3b", "#2a6bb5"   # red = pays more, blue = pays less
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e1e0d9"

fleet = m.load_fleet()
n = len(fleet)
rng = np.random.default_rng(m.SEED)
gaps = []
for _ in range(m.N_RUNS):
    cf = rng.uniform(*m.CF_RANGE, n)
    gaps.append(m.by_tier(fleet, allowance_gap(fleet, cf)).to_numpy())
cost = pd.DataFrame(gaps, columns=m.TIERS) / 1e6 * CARBON_TAX_USD   # $M per year

med = cost.median()
lo, hi = cost.quantile(.05), cost.quantile(.95)
labels = ["Small\n<100 MW", "Mine-mouth\n>=100 MW", "Mid\n100-400 MW", "Large\n>400 MW"]

fig, ax = plt.subplots(figsize=(8, 5), facecolor="#fcfcfb")
ax.set_facecolor("#fcfcfb")
x = np.arange(len(m.TIERS))
colors = [PAY_MORE if v > 0 else PAY_LESS for v in med]
ax.bar(x, med, width=0.5, color=colors)
ax.errorbar(x, med, yerr=[med - lo, hi - med], fmt="none", ecolor=INK, capsize=4, linewidth=1)
ax.axhline(0, color="#c3c2b7", linewidth=1)
for xi, v in zip(x, med):
    txt = f"{v:+.1f}\n" + ("pays more" if v > 0 else "pays less")
    ax.annotate(txt, (xi, v), xytext=(0, 10 if v > 0 else -10), textcoords="offset points",
                ha="center", va="bottom" if v > 0 else "top", fontsize=10, color=INK)
ax.set_xticks(x)
ax.set_xticklabels(labels, color=INK)
ax.set_ylabel("Change in net cost vs single benchmark ($M per year)", color=MUTED)
ax.set_ylim(min(lo.min() * 1.0, -12) - 6, hi.max() + 8)
ax.set_title(f"Who pays when benchmarks are tiered by plant size\n"
             f"at the legal carbon tax of ${CARBON_TAX_USD:g}/t (Rp30,000), real GEM fleet, 147 units",
             fontsize=11, color=INK)
ax.grid(axis="y", color=GRID, linewidth=0.8)
ax.set_axisbelow(True)
ax.spines[["top", "right"]].set_visible(False)
ax.spines[["left", "bottom"]].set_color("#c3c2b7")
ax.tick_params(colors=MUTED)
fig.text(0.01, 0.01, "Reference price, not an observed market price. Bars: median of 1000 capacity-factor "
         "draws; whiskers: 5th-95th pct.", fontsize=7.5, color=MUTED)
fig.tight_layout(rect=(0, 0.03, 1, 1))
m.OUT_FIG.parent.mkdir(exist_ok=True)
out = m.OUT_FIG.parent / "stage4b_price.png"
fig.savefig(out, dpi=150)
print(f"Saved {out.relative_to(m.ROOT)}")
