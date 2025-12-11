# ENOE_PANEL usage guide

This guide summarizes how to run the harmonization and panel construction for ENOE 2005–2025 and highlights instrument differences.

## 1) Configure paths
- Edit `Do-files/00 Master.do`:
  - Set the `$path` global to your ENOE root. Use forward slashes on macOS/Linux.
  - Ensure per-user blocks match your username/hostname if used.
- GLD folder layout must follow the pattern: `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M/Data/Stata` and `.../Programs`.

## 2) Run the main pipeline
In Stata (16+):
```stata
do "Do-files/00 Master.do"
```
Steps executed:
1. `01_ENOE_Harmonization.do` — runs each quarter’s GLD program (skips 2020.Q2).
2. `02_Append_ENOE_Surveys.do` — appends harmonized quarters, builds panel IDs/flags.
3. `03_Construct_panel_of_workers.do` — builds the balanced rotating panel.
4. `04_Figure_08.do`, `05_Annex_Table_6.do`, `06_Annex_Table_8.do` — exports figures/tables to Excel.

Logs are written to `Do-files/Logs/`.

## 3) Optional parallel run
- `PANEL/DO/00_Process_ENOE_quarterly_data.do` and `01_Append_ENOE_quarterly_data.do` can spawn batch do-files per year and execute via `myscript.sh` (macOS) or `.bat` (Windows). Use only if paths/users are adapted to your machine.

## 4) Instrument differences (handle defensively)
- **Working hours**: Older instruments use `p5c_thrs`/`p5e_thrs`; newer use `p5b_thrs`/`p5d_thrs`. Defensive logic exists in 2024/2025 scripts; mirror it if extending.
- **Months worked**: Older use `p5g*`; newer use `p5f*`. Defensive logic exists in 2024/2025 scripts; mirror it if extending.
- **Firm size (primary job)**: Q1 uses `p3q`; Q2–Q4 use `p3l`. Adjust if you add new years.
- **Geographic codes**: From 2025.Q3, INEGI renames `ent`→`cve_ent` (and `mun`/`loc`). Normalize after `rename *, lower;` before folio/subnat IDs.
- **Weights/strata**: Some quarters use `fac_np`/`est_d`, others `fac`/`est_d_tri`. Add `cap confirm var` fallbacks if missing.
- **Missing quarter**: 2020.Q2 is absent and is skipped by counter logic.

## 5) Required auxiliary files
Ensure lookup files are present in each quarter’s Stata folder when needed (e.g., `SCIAN_07_3D_ISIC_4.dta`, `SINCO_11_ISCO_08.dta`) to avoid merge failures.

## 6) Outputs
- Harmonized quarterly `.dta` in each quarter’s `Data/Harmonized`.
- Appended full sample: `PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`.
- Balanced panel: `PANEL/DATA/MEX_2005_2023_PANEL_QUARTER.dta`.
- Excel: `Output/FINAL figures for MEX PEA.xlsx`, `Output/FINAL tables for MEX PEA.xlsx`.

## 7) Troubleshooting
- Missing variable errors (e.g., `p5b_thrs`, `p5f1`, `ent`): add `cap confirm var` branches and normalize names early.
- Path errors: confirm `$path` in `00 Master.do` and folder layout.
- 2020.Q2 absence: expected; the pipeline skips counter 62.
