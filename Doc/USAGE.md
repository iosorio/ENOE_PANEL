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
- **Labor concepts depend on questionnaire module**:
  - Expanded module (typically Q1): `p3i` is union membership, `p3j` is contract, `p3m4/p3m5` feed `socialsec/healthins`.
  - Basic module (typically Q2–Q4): `p3i` is contract, and union/`p3m*` benefits are not asked.
  - Harmonization now resolves this by variable presence (`cap confirm variable p3j/p3m4/p3m5`) instead of hardcoded quarter logic.
- **Historical exceptions exist in early rounds** (for example, some non-Q1 rounds still use the expanded structure), so variable-presence checks are preferred over quarter-based assumptions.
- **Labor cleanup guard**: the min-age cleanup loop now checks variable existence before replacing values, preventing `r(111)` errors when module-specific variables are absent.
- **Audit reference**: quarter-level metadata audit used for this rollout is stored at `Do-files/quarterly_agent/state/audits/labor_metadata_2005Q1_2025Q3_v2.csv`.
- **Geographic codes**: From 2025.Q3, INEGI renames `ent` -> `cve_ent` (and `mun`/`loc`). Normalize after `rename *, lower;` before folio/subnat IDs.
- **Weights/strata**: Some quarters use `fac_np`/`est_d`, others `fac`/`est_d_tri`. Add `cap confirm var` fallbacks if missing.
- **Missing quarter**: 2020.Q2 is absent and is skipped by counter logic.

## 5) Crosswalk scripts
Canonical crosswalk scripts live in `Doc/Source_Packages/programs/`. Set `ENOE_DOCS` to the folder containing:
- `SCIAN_18_ISIC_4.xlsx`
- `SCIAN_07_ISIC_4.xlsx`
- `tablas_comparativas.xlsx`

Crosswalk granularity used in harmonization:
- `p4a` / `p7c` are 4-digit source codes, and ENOE harmonization maps industry through **3-digit** SCIAN keys first.
- Preferred file: `SCIAN_18_3D_ISIC_4.dta`.
- Fallback file: `SCIAN_07_3D_ISIC_4.dta`.
- Why 3-digit:
  - ENOE contains many 4-digit aggregate/unspecified endings that do not have stable exact 4-digit matches.
  - 3-digit mapping preserves high coverage and historical continuity across rounds.
- Practical rule:
  - code `abcd` is first merged as prefix `abc`;
  - if `abc` is missing in the selected crosswalk, harmonization falls back to prefix `ab` to assign `industrycat10` (and `industrycat10_2`) only;
  - `industrycat_isic` can still remain missing when no 3-digit SCIAN->ISIC mapping exists.

## 6) Shared Stata helpers
- `Do-files/ent_mun_label.do` is now the shared helper for subnational labels. Harmonization scripts set `path_in_do` to `\`server'/Do-files`.

## 7) Quality checks
- Canonical GLD Q-checks live in `Do-files/Quality_Checks/`.
- Sequential runner: `Do-files/Quality_Checks/00_Run_All_Sequential.do`
- Parallel runner (optional): `Do-files/Quality_Checks/00_Run_All_Parallel.do`
- Outputs are written to `Output/Quality_Checks/by-year/YYYY/QX/`.
- Python qcheck-style runner: `Do-files/quality_checks_py/qcheck_harmonization.py`
  - Single dataset:
    - `python Do-files/quality_checks_py/qcheck_harmonization.py --dataset <harmonized_dta> --reports static,basic,categoric --profile full`
  - Batch:
    - `python Do-files/quality_checks_py/qcheck_harmonization.py --batch --start-year 2005 --end-year 2025 --reports static,basic,categoric --profile full`
  - Outputs are written to `Output/Quality_Checks_Py/by-year/YYYY/QX/`.

## 8) Outputs
- Harmonized quarterly `.dta` in each quarter’s `Data/Harmonized/`.
- Appended full sample (parameterized): `PANEL/DATA/MEX_<start>_<end>Q<q>_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`.
- Balanced panel (parameterized): `PANEL/DATA/MEX_<start>_<end>Q<q>_PANEL_QUARTER.dta`.
- Latest aliases:
  - `PANEL/DATA/MEX_ENOE_V01_M_V06_A_GLD_FULLSAMPLE_latest.dta`
  - `PANEL/DATA/MEX_PANEL_QUARTER_latest.dta`
- Current full-window example (this project): `MEX_2005_2025Q3_*`.
- Excel outputs are not produced by the current pipeline.

## 9) Troubleshooting
- Missing variable errors (e.g., `p5b_thrs`, `p5f1`, `ent`): add `cap confirm var` branches and normalize names early.
- Path errors: confirm `$path` in `00 Master.do` and folder layout.
- 2020.Q2 absence: expected; the pipeline skips counter 62.
- Quarterly agent parallel rebuild now marks 2020.Q2 as `skipped` (expected), not `failed`.
- Phase-2 wrapper now treats Stata runtime codes (`r(<code>)`) in logs as failures even when process return code is zero.
