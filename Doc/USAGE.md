# ENOE_PANEL usage guide

This guide summarizes how to run the ENOE harmonization and panel construction for 2005–2025 and highlights key instrument differences.

## 1) Configure paths
- Edit `Do-files/00 Master.do`:
  - Set the `$path` global to your ENOE root. Use forward slashes on macOS/Linux.
  - Ensure any per-user blocks match your username/hostname if used.
- The GLD folder layout must follow the pattern:
  - `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M/Data/Original`
  - `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M/Data/Stata`
  - `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M/Programs`

## 2) Run the main pipeline
In Stata (16+):
```stata
do "Do-files/00 Master.do"
```
Steps executed:
1. `01_ENOE_Harmonization.do` — runs each quarter’s GLD program (skips 2020.Q2).
2. `02_Append_ENOE_Surveys.do` — appends harmonized quarters, builds panel IDs/flags.
3. `03_Construct_panel_of_workers.do` — builds the balanced rotating panel.

Logs are written to `Do-files/Logs/`.

## 3) Optional parallel run
- `PANEL/DO/00_Process_ENOE_quarterly_data.do` and `01_Append_ENOE_quarterly_data.do` can spawn batch do-files per year and execute via `myscript.sh` (macOS) or `.bat` (Windows). Use only if paths/users are adapted to your machine.

## 4) Instrument differences (handle defensively)
- **Working hours**: Older instruments use `p5c_thrs`/`p5e_thrs`; newer use `p5b_thrs`/`p5d_thrs`.
- **Months worked**: Older use `p5g*`; newer use `p5f*`.
- **Firm size (primary job)**: Q1 uses `p3q`; Q2–Q4 use `p3l`.
- **Geographic codes**: From 2025.Q3, INEGI renames `ent` -> `cve_ent` (and `mun`/`loc`). Normalize after `rename *, lower;` before folio/subnat IDs.
- **Weights/strata**: Some quarters use `fac_np`/`est_d`, others `fac`/`est_d_tri`. Add `cap confirm var` fallbacks if missing.
- **Missing quarter**: 2020.Q2 is absent and is skipped by counter logic.

## 5) Crosswalk scripts
Canonical crosswalk scripts live in `Doc/Source_Packages/programs/`. Set `ENOE_DOCS` to the folder containing:
- `SCIAN_18_ISIC_4.xlsx`
- `SCIAN_07_ISIC_4.xlsx`
- `tablas_comparativas.xlsx`

## 6) Shared Stata helpers
- `Do-files/ent_mun_label.do` is now the shared helper for subnational labels. Harmonization scripts set `path_in_do` to `\`server'/Do-files`.

## 7) Quality checks
- Canonical GLD Q-checks live in `Do-files/Quality_Checks/`.
- Sequential runner: `Do-files/Quality_Checks/00_Run_All_Sequential.do`
- Parallel runner (optional): `Do-files/Quality_Checks/00_Run_All_Parallel.do`
- Outputs are written to `Output/Quality_Checks/by-year/YYYY/QX/`.

## 8) Outputs
- Harmonized quarterly `.dta` in each quarter’s `Data/Harmonized/`.
- Appended full sample: `PANEL/DATA/MEX_2005_2023_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`.
- Balanced panel: `PANEL/DATA/MEX_2005_2023_PANEL_QUARTER.dta`.
- Excel outputs are not produced by the current pipeline.

## 9) Troubleshooting
- Missing variable errors (e.g., `p5b_thrs`, `p5f1`, `ent`): add `cap confirm var` branches and normalize names early.
- Path errors: confirm `$path` in `00 Master.do` and folder layout.
- 2020.Q2 absence: expected; the pipeline skips counter 62.
