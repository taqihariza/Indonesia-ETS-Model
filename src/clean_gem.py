"""Stage 4b step 1: clean the GEM Global Coal Plant Tracker (July 2026) to an Indonesia CSV.

Data: Global Energy Monitor, Global Coal Plant Tracker, July 2026 release (CC BY 4.0).
Usage: python src/clean_gem.py path/to/Global-Coal-Plant-Tracker-July-2026.xlsx
"""
import sys
import pandas as pd

src = sys.argv[1]
out = "data/gem_indonesia_operating_noncaptive.csv"

df = pd.read_excel(src, sheet_name="Units")

keep = df[
    (df["Country/Area"] == "Indonesia")
    & (df["Status"].astype(str).str.lower() == "operating")
    & (df["Captive"].isna())
].copy()

cols = {
    "GEM unit/phase ID": "gem_unit_id",
    "Plant name": "plant_name",
    "Unit name": "unit_name",
    "Capacity (MW)": "capacity_mw",
    "Status": "status",
    "Start year": "start_year",
    "Combustion technology": "technology",
    "Minemouth": "minemouth",
    "Capacity factor": "capacity_factor_gem_default",
    "Heat rate (Btu per kWh)": "heat_rate_btu_per_kwh",
    "Emission factor (kg of CO2 per TJ)": "emission_factor_kg_per_tj",
    "Annual CO2 (million tonnes / annum)": "annual_co2_mt_gem_modelled",
}
keep = keep[list(cols)].rename(columns=cols)
keep["minemouth"] = keep["minemouth"].eq("yes")          # True / False
keep = keep.sort_values(["plant_name", "unit_name"]).reset_index(drop=True)
keep.to_csv(out, index=False)

print(f"Rows written: {len(keep)}  ->  {out}\n")
print("Duplicate unit IDs:", keep["gem_unit_id"].duplicated().sum())
print("Columns with missing values:", keep.columns[keep.isna().any()].tolist(), "\n")

mw = keep["capacity_mw"]
keep["size_group"] = pd.cut(mw, [0, 99.999, 1e9], labels=["<100 MW", ">=100 MW"])
print("Total capacity (MW):", mw.sum(), " | Total GEM CO2 (Mt/yr): %.1f" % keep["annual_co2_mt_gem_modelled"].sum(), "\n")
print("Units by size group x minemouth:")
print(pd.crosstab(keep["size_group"], keep["minemouth"], margins=True), "\n")
print("Exactly 100 MW:", (mw == 100).sum(), "| exactly 400 MW:", (mw == 400).sum(), "\n")
print("Technology:\n", keep["technology"].value_counts(), "\n")
print("Capacity factor values:", keep["capacity_factor_gem_default"].unique())
