# ENOE_PANEL : Mexico ENOE (Encuesta Nacional de Ocupación y Empleo) Harmonization and Panel Construction.

About: Harmonization and panel construction scripts for Mexico’s ENOE (Encuesta Nacional de Ocupación y Empleo) using the [World Bank Global Labor Database](url:https://github.com/worldbank/gld) template. The codebase spans 2005.Q1–2025.Q3 and generates harmonized quarterly microdata, a rotating worker panel, and tabulations/figures for analysis.

## Repository layout
- `Do-files/` — main pipeline in Stata:
  - `00 Master.do` orchestrates the full run.
  - `01_ENOE_Harmonization.do` executes GLD harmonization for each quarter.
  - `02_Append_ENOE_Surveys.do` appends all harmonized quarters, builds panel IDs/flags.
  - `03_Construct_panel_of_workers.do` builds the balanced rotating panel.
  - `04_Figure_08.do`, `05_Annex_Table_6.do`, `06_Annex_Table_8.do` export outputs to Excel.
  - Label helpers: `ent_mun_label.do`, `lblc_mnpio.do`.
- `MEX_YYYY_ENOE-QX/` — per-quarter folders with GLD Programs/Data.
- `PANEL/` — derived data (`PANEL/DATA/*.dta`) and auxiliary scripts.
- `Output/` — Excel outputs for figures/tables.

## Prerequisites
- Stata 16 or newer (tested with Stata MP).
- Sufficient disk for raw ENOE microdata and harmonized outputs.
- Local copies of the ENOE raw/Stata files organized per GLD expectations.

## Quick start
1) Clone or open the repository.
2) Set the base path in `Do-files/00 Master.do` (and in any per-user path logic if needed) to your local ENOE data root. Use forward slashes on macOS/Linux.
3) Run from Stata: `do "Do-files/00 Master.do"`. This:
   - Harmonizes each quarter (except 2020.Q2, which is missing).
   - Appends and constructs panel flags/IDs.
   - Builds the balanced rotating panel.
   - Writes outputs to `Output/FINAL ... .xlsx`.

### Parallel option (optional)
`PANEL/DO/00_Process_ENOE_quarterly_data.do` and `01_Append_ENOE_quarterly_data.do` include parallel run logic that spawns year-specific batch do-files and executes them via `myscript.sh` (macOS) or `.bat` (Windows). Use only if the path/user blocks match your environment.

## Instrument differences to be aware of
- **Working hours**: Older instruments use `p5c_thrs` (fallback `p5e_thrs`); newer ones use `p5b_thrs` (fallback `p5d_thrs`). Defensive logic is present in 2024/2025 scripts.
- **Months worked**: Older instruments use `p5g*`; newer use `p5f*`. Defensive logic is present in 2024/2025 scripts.
- **Firm size (primary job)**: Q1 uses `p3q` (older code); Q2–Q4 use `p3l` (newer). 2024/2025 Q1 files have been aligned to `p3q`.
- **Geographic codes**: Starting 2025.Q3 INEGI renamed `ent` → `cve_ent` (and similarly `mun`/`loc`). 2025.Q3 harmonization normalizes these after `rename *, lower;` so folios/subnat IDs remain consistent.
- **Weights/strata**: Some quarters use `fac_np`/`est_d`, others `fac`/`est_d_tri`. If you see missing-variable errors on weights/strata, mirror the defensive pattern used elsewhere.
- **Missing quarter**: 2020.Q2 is absent (COVID-19); the pipeline skips counter 62.

## Outputs
- Harmonized quarterly microdata per survey in `.../Data/Harmonized/`.
- Appended full sample: `PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`.
- Balanced panel: `PANEL/DATA/MEX_2005_2023_PANEL_QUARTER.dta`.
- Excel outputs: `Output/FINAL figures for MEX PEA.xlsx` and `Output/FINAL tables for MEX PEA.xlsx`.

## Logging and reproducibility
- Each step writes a log to `Do-files/Logs/`.
- Scripts assume lowercase variable names after `rename *, lower;`.
- Keep the directory structure intact (GLD format) for relative paths to resolve.
- `sample_size_audit.csv` records HH/IND sample sizes computed from raw SDEMT inputs (HH = distinct `folioh`, IND = row count after `r_def==0` and `c_res in {1,3}`); updated 2026-01-08.
- `Do-files/sample_size_audit/sample_size_audit.py` recomputes those sample sizes from raw SDEMT and can update the tags: `python Do-files/sample_size_audit/sample_size_audit.py --update`.

## Harmonization consistency review (2026-01-08)
- Reviewed 82 `MEX_*_ENOE_V01_M_V06_A_GLD_ALL.do` files for metadata consistency.
- Core metadata are consistent: `countrycode=MEX`, `survname=ENOE`, `survey=LFS`, `isco_version=isco_2008`, `isic_version=isic_4`, `harmonization=GLD`.
- `year` and `int_year` match the `local year` macro in each file; `wave` matches the quarter in the folder name.
- Expected version shifts are present: `icls_v` is `ICLS-13` (2005-2012) then `ICLS-18` (2013-2025); `isced_version` is `isced_1997` (2005-2011) then `isced_2011` (2012-2025).
- Fixes applied: 2024/2025 `year` and `int_year` were corrected from 2023, and 2024/2025 Q1-Q3 `wave` values were corrected from Q4.

## Contributing
- Keep edits ASCII-only unless the file already contains accents/Unicode.
- Follow existing naming/path conventions.
- When introducing new instrument differences, add defensive `cap confirm var ...` checks and normalize variable names early in each block.
