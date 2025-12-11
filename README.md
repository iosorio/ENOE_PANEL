# ENOE_PANEL

Harmonization and panel construction scripts for Mexico’s ENOE (Encuesta Nacional de Ocupación y Empleo) using the World Bank GLD template. The repository runs from 2005.Q1 through 2025.Q3 and produces harmonized quarterly microdata, a rotating worker panel, and tabulations/figures used in downstream analysis.

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

## Contributing
- Keep edits ASCII-only unless the file already contains accents/Unicode.
- Follow existing naming/path conventions.
- When introducing new instrument differences, add defensive `cap confirm var ...` checks and normalize variable names early in each block.
