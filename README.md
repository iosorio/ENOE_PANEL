# ENOE_PANEL: Mexico ENOE Harmonization and Panel Construction

Harmonization and panel construction scripts for Mexico’s ENOE (Encuesta Nacional de Ocupacion y Empleo) using the [World Bank Global Labor Database](https://github.com/worldbank/gld) template. The codebase spans 2005.Q1–2025.Q3 and generates harmonized quarterly microdata plus a rotating worker panel.

## Contents
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Supported flows](#supported-flows)
- [Flow A: Python+Stata (recommended)](#flow-a-pythonstata-recommended)
- [Flow B: Stata-only](#flow-b-stata-only)
- [Quarterly agent automation (phases 1-4)](#quarterly-agent-automation-phases-1-4--poverty-sync)
- [Optional parallel run](#optional-parallel-run)
- [Inputs and outputs](#inputs-and-outputs)
- [Instrument differences to be aware of](#instrument-differences-to-be-aware-of)
- [SCIAN 4D vs 3D vs 2D crosswalk logic](#scian-4d-vs-3d-vs-2d-crosswalk-logic)
- [Logging and reproducibility](#logging-and-reproducibility)
- [Archived legacy files](#archived-legacy-files-2026-03-02)
- [Harmonization consistency review (2026-01-08)](#harmonization-consistency-review-2026-01-08)
- [Contributing](#contributing)

## Repository layout
- `Do-files/` — main Stata pipeline:
  - `00_Master.do` is the Stata-only entrypoint.
  - `01_ENOE_Harmonization.do` executes GLD harmonization for each quarter.
  - `02_Append_ENOE_Surveys.do` appends all harmonized quarters, builds panel IDs/flags.
  - `03_Construct_panel_of_workers.do` builds the balanced rotating panel.
  - Label helper in active use: `ent_mun_label.do`.
- `Do-files/quarterly_agent/` — quarterly automation scripts:
  - `phase1_detect_download.py` detects/releases and downloads ENOE ZIPs.
  - `phase1b_sync_poverty_lines.py` syncs INEGI poverty lines and patches the target harmonization do-file.
  - `phase2_scaffold_quarter.py` scaffolds new quarter folders from prior templates.
  - `phase2_run_stata_pipeline.py` runs extract/harmonize/append/panel (+ optional QC).
  - `phase4_schema_diff.py` compares schemas across two selected quarters.
  - `run_quarterly_agent.py` orchestrates the end-to-end run.
  - `state/` stores JSON run manifests for reproducibility and diagnostics.
- `MEX_YYYY_ENOE-QX/` — per-quarter folders with GLD Programs/Data.
- `PANEL/` — derived data (`PANEL/DATA/*.dta`) and auxiliary scripts.
- `Output/` — legacy outputs (if present).
- `Doc/Documentation/` — consolidated reference documentation, indexed at `Doc/Documentation/INDEX.md`.
- `Doc/Source_Packages/` — canonical crosswalk scripts (`programs/`) and index at `Doc/Source_Packages/INDEX.md`. Set `ENOE_DOCS` to the folder containing `SCIAN_18_ISIC_4.xlsx`, `SCIAN_07_ISIC_4.xlsx`, and `tablas_comparativas.xlsx` before running those scripts.
- `Doc/poverty_lines_inegi/` — INEGI poverty line inputs and generated monthly/quarterly tables used by harmonization.
- `Do-files/ent_mun_label.do` — shared geographic label helper now referenced by harmonization scripts.
- `Do-files/Quality_Checks/` — canonical GLD quality checks and runners (see `Do-files/Quality_Checks/INDEX.md`).
- `Do-files/quality_checks_py/` — Python qcheck-style quality checks (`static`, `basic`, `categoric`) with batch support.
- `Output/Quality_Checks/` — generated quality-check outputs by year/quarter.
- `Output/Quality_Checks_Py/` — generated outputs from the Python qcheck-style runner.
- `archive_legacy/` — non-destructive archive for deprecated scripts and generated temp wrappers.

## Prerequisites
- Stata 16 or newer (tested with Stata MP).
- Sufficient disk for raw ENOE microdata and harmonized outputs.
- Local copies of the ENOE raw/Stata files organized per GLD expectations.

## Supported flows
Two execution flows are supported and kept in parallel:
- `Flow A (Python+Stata)`: orchestration, schema checks, poverty-line sync, and pipeline execution via Python wrappers plus Stata.
- `Flow B (Stata-only)`: direct Stata execution from `Do-files/00_Master.do` and canonical Stata Q-check scripts.

## Flow A: Python+Stata (recommended)
Run from repository root:

```bash
python3 Do-files/quarterly_agent/run_quarterly_agent.py \
  --years 2025 \
  --target-year 2025 \
  --target-quarter 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp \
  --always-run-pipeline
```

This flow covers:
- quarter detection/download,
- poverty-line sync,
- scaffold/schema checks,
- harmonization + append + panel (+ optional QC).

## Flow B: Stata-only
1) Set path in `Do-files/00_Master.do`.
2) In `Do-files/00_Master.do`, ensure step 2 and step 3 are uncommented if you want full sample and panel outputs.
3) Run in Stata:

```stata
do "Do-files/00_Master.do"
```

For Q-checks in Stata-only mode:

```stata
do "Do-files/Quality_Checks/00_Run_All_Sequential.do"
```

## Quarterly agent automation (phases 1-4 + poverty sync)
Run from repository root:

```bash
python3 Do-files/quarterly_agent/run_quarterly_agent.py \
  --years 2025 \
  --target-year 2025 \
  --target-quarter 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp \
  --always-run-pipeline
```

Useful flags:
- `--dry-run` validates orchestration without changing data outputs.
- `--run-qc` executes QC after panel construction.
- `--fail-on-schema-breaking` stops the run if either schema check is breaking.
- `--force-scaffold` recreates the quarter scaffold even if the target folder already exists.
- `--skip-poverty-sync` bypasses INEGI poverty-line refresh and do-file patch (not recommended for production runs).

Poverty-line sync executed by default:
- Pulls monthly series from INEGI sources (preferred: INEGI-hosted XLSX/ZIP; fallback: INEGI indicator API).
- Writes canonical tables:
  - `Doc/poverty_lines_inegi/poverty_lines_monthly.csv`
  - `Doc/poverty_lines_inegi/poverty_lines_quarterly.csv`
- Patches the target quarter harmonization do-file to set only the current quarter scalars from `poverty_lines_quarterly.csv`.

Schema checks executed by default:
- `schema_prev`: target quarter versus immediately previous quarter.
- `schema_yoy`: target quarter versus same quarter in the prior year.
- If a baseline quarter is unavailable (for example very early historical quarters), that check is marked `skipped_missing_base`.

## Optional parallel run
Use `Do-files/quarterly_agent/phase2_rebuild_range_parallel.py` to rebuild quarter harmonizations in parallel and then run one final append/panel step.

OneDrive safety gate (enabled by default):
- Parallel run is blocked until an acknowledgement file exists and is fresh.
- Default ack file:
  - `Do-files/quarterly_agent/state/locks/onedrive_paused.ok`
- Recommended flow:
  1. Pause OneDrive sync manually from menu bar/tray.
  2. Confirm pause with:

```bash
touch Do-files/quarterly_agent/state/locks/onedrive_paused.ok
```

  3. Run parallel rebuild:

```bash
python3 Do-files/quarterly_agent/phase2_rebuild_range_parallel.py \
  --start-year 2021 \
  --start-quarter 1 \
  --end-year 2025 \
  --end-quarter 3 \
  --workers 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp
```

Useful flags:
- `--wait-for-onedrive` waits for ack file instead of exiting immediately.
- `--onedrive-ack-max-age-minutes 240` controls freshness tolerance.
- `--continue-on-error` completes all submitted harmonization jobs even if some fail.
- `--skip-finalize` runs only parallel harmonization jobs.

Local network Mac example (same folder structure):

```bash
# From your main machine, sync code/data to the other Mac (replace <REMOTE_IP>)
rsync -azP --delete \
  "/Users/israel/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL/" \
  "israel@<REMOTE_IP>:/Users/israel/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL/"

# SSH into the remote Mac and run the parallel rebuild there
ssh israel@<REMOTE_IP> '
cd "/Users/israel/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL" &&
touch Do-files/quarterly_agent/state/locks/onedrive_paused.ok &&
python3 Do-files/quarterly_agent/phase2_rebuild_range_parallel.py \
  --start-year 2021 \
  --start-quarter 1 \
  --end-year 2025 \
  --end-quarter 3 \
  --workers 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp
'
```

## Python quality checks (qcheck-style)
Run a single quarter:

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --dataset MEX_2025_ENOE-Q3/MEX_2025_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_2025_ENOE_V01_M_V06_A_GLD_ALL.dta \
  --reports static,basic,categoric \
  --profile full
```

Run all available quarters:

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --batch \
  --start-year 2005 \
  --end-year 2025 \
  --reports static,basic,categoric \
  --profile full
```

See `Do-files/quality_checks_py/README.md` for full options, output schema, and custom-rule support.

## QC triage (short guide)
Prioritize QC findings in this order:

1. `Flag = 1` (or `severity = 1` in Python): must-fix before trusting outputs.
2. `Flag = 99`: investigate; can be expected in some quarters but must be reviewed.
3. Within each group, rank by impact using `failed_ratio` first, then `failed_n`.
4. Fix module order: `Overall` and `Survey & ID` first, then `Geography/Demography`, then `Labour`.
5. Operational thresholds:
   - `failed_ratio > 5%` on critical variables: block release.
   - `0.5% to 5%`: fix before final panel if feasible.
   - `<0.5%`: targeted review and document decision.

## Inputs and outputs
Inputs
- Raw ENOE data should be available under each quarter at `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M/Data/Original` and `.../Data/Stata` following the GLD layout.

Outputs
- Harmonized quarterly microdata in each quarter’s `Data/Harmonized/`.
- Appended full sample (dynamic): `PANEL/DATA/MEX_<start>_<endYear>Q<endQ>_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`.
- Balanced panel (dynamic): `PANEL/DATA/MEX_<start>_<endYear>Q<endQ>_PANEL_QUARTER.dta`.
- Stable aliases for latest run:
  - `PANEL/DATA/MEX_ENOE_V01_M_V06_A_GLD_FULLSAMPLE_latest.dta`
  - `PANEL/DATA/MEX_PANEL_QUARTER_latest.dta`
- Excel outputs are not produced by the current pipeline.

## Instrument differences to be aware of
- **Working hours**: Older instruments use `p5c_thrs` (fallback `p5e_thrs`); newer ones use `p5b_thrs` (fallback `p5d_thrs`). Defensive logic is present in 2024/2025 scripts.
- **Months worked**: Older instruments use `p5g*`; newer use `p5f*`. Defensive logic is present in 2024/2025 scripts.
- **Firm size (primary job)**: Q1 uses `p3q` (older code); Q2–Q4 use `p3l` (newer). 2024/2025 Q1 files have been aligned to `p3q`.
- **Geographic codes**: Starting 2025.Q3 INEGI renamed `ent` -> `cve_ent` (and similarly `mun`/`loc`). 2025.Q3 harmonization normalizes these after `rename *, lower;` so folios/subnat IDs remain consistent.
- **Weights/strata**: Some quarters use `fac_np`/`est_d`, others `fac`/`est_d_tri`. If you see missing-variable errors on weights/strata, mirror the defensive pattern used elsewhere.
- **Missing quarter**: 2020.Q2 is absent (COVID-19); the pipeline skips counter 62.

## SCIAN 4D vs 3D vs 2D crosswalk logic
- ENOE source variables `p4a` (main job) and `p7c` (second job) are 4-digit national industry codes.
- From 2023.Q1 onward, ENOE metadata documents the national classifier as **SCIAN Hogares 2018**.
- Two crosswalk granularities exist conceptually:
  - `4-digit` matching (`SCIAN_18_ISIC_4`): exact `SCIAN4 -> ISIC` mapping.
  - `3-digit` matching (`SCIAN_18_3D_ISIC_4`): map on first 3 digits (`SCIAN3 -> ISIC`).
- Current harmonization policy in all quarterly do-files uses **3-digit matching** for ENOE because many observed ENOE codes are aggregate/unspecified at the 4th digit (or use addendum endings), which reduces exact 4-digit coverage.
- Quarter do-file logic:
  - Prefer `Data/Stata/SCIAN_18_3D_ISIC_4.dta` when available.
  - Fallback to `Data/Stata/SCIAN_07_3D_ISIC_4.dta` for backward compatibility.
- If a code is still unresolved after 3-digit merge, a **2-digit SCIAN fallback** is applied to assign `industrycat10`/`industrycat10_2` only.
- 2-digit fallback mapping:
  - `11 -> 1` (Agriculture)
  - `21 -> 2` (Mining)
  - `22 -> 4` (Public utilities)
  - `23 -> 5` (Construction)
  - `31/32/33 -> 3` (Manufacturing)
  - `43/46/72 -> 6` (Commerce)
  - `48/49/51 -> 7` (Transport and Communications)
  - `52/53/54/55/56 -> 8` (Financial and Business Services)
  - `93 -> 9` (Public Administration)
  - `61/62/71/81/97/98/99 -> 10` (Other Services, Unspecified)
- Practical implication:
  - If a code like `6132` appears, harmonization first attempts prefix `613` via 3-digit crosswalk.
  - If `613` is absent, fallback uses `61`, so `industrycat10` is still assigned.
  - `industrycat_isic` may remain missing when no 3-digit SCIAN->ISIC mapping exists.

## Logging and reproducibility
- Each step writes a log to `Do-files/Logs/`.
- Quarterly agent run manifests are stored under `Do-files/quarterly_agent/state/`:
  - `state/agent_runs/agent_run_<timestamp>.json`
  - `state/poverty/phase1b_poverty_sync_<timestamp>.json`
  - `state/runs/phase2_run_<year>Q<quarter>_<timestamp>.json`
  - `state/rebuild_parallel/phase2_rebuild_parallel_<timestamp>.json`
  - `state/schema/phase4_schema_<year>Q<quarter>_<comparison>_<timestamp>.json` (`comparison` is typically `prev` or `yoy`)
- Scripts assume lowercase variable names after `rename *, lower;`.
- Keep the directory structure intact (GLD format) for relative paths to resolve.
- Harmonization scripts now set `path_in_do` to `\`server'/Do-files` for `ent_mun_label.do`.
- `sample_size_audit.csv` records HH/IND sample sizes computed from raw SDEMT inputs (HH = distinct `folioh`, IND = row count after `r_def==0` and `c_res in {1,3}`); updated 2026-01-08.
- `Do-files/sample_size_audit/sample_size_audit.py` recomputes those sample sizes from raw SDEMT and can update the tags: `python Do-files/sample_size_audit/sample_size_audit.py --update`.

## Archived legacy files (2026-03-02)
To reduce clutter while keeping backward traceability, deprecated/temporary artifacts were moved (not deleted) to:
- `archive_legacy/20260302_094547_dualflow_cleanup/`

Manifest of all moved files:
- `archive_legacy/20260302_094547_dualflow_cleanup/move_manifest.txt`

Archived set includes:
- legacy `DO/` scripts,
- deprecated `Do-files/lblc_mnpio.do`,
- generated wrappers `Do-files/quarterly_agent/state/runs/tmp_*.do`,
- generated QC launcher `Do-files/Quality_Checks/batch/myscript.sh`.

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
