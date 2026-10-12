# Data: Indonesia coal fleet (Stage 4b)

**Source:** Global Energy Monitor, *Global Coal Plant Tracker*, July 2026 release.
Licence: CC BY 4.0 (attribution required). https://globalenergymonitor.org/projects/global-coal-plant-tracker/

**File:** `gem_indonesia_operating_noncaptive.csv` (147 units, made by `src/clean_gem.py`)

**Filter:** Country/Area = Indonesia, Status = operating, Captive = blank (non-captive).

| Column | Real or assumed? |
|---|---|
| gem_unit_id, plant_name, unit_name | Real (GEM unit list) |
| capacity_mw, start_year, technology | Real (GEM) |
| minemouth | Real (GEM flag; True = yes) |
| heat_rate_btu_per_kwh, emission_factor_kg_per_tj | GEM estimates, not measured |
| capacity_factor_gem_default | Assumed: flat 0.64 for every unit, not data |
| annual_co2_mt_gem_modelled | GEM modelled (capacity x 0.64 x intensity), not measured |

GEM has no measured generation or emissions. Abatement costs are not public and are assumptions in the model.
