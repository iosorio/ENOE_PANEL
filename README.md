# ENOE_PANEL: Mexico ENOE Harmonization and Panel Construction

Harmonization and panel construction scripts for Mexico’s ENOE (Encuesta Nacional de Ocupacion y Empleo) using the [World Bank Global Labor Database](https://github.com/worldbank/gld) template. The codebase spans 2005.Q1–2025.Q3 and generates harmonized quarterly microdata plus a rotating worker panel.

## Contents
- [Repository layout](#repository-layout)
- [Prerequisites](#prerequisites)
- [Quick start](#quick-start)
- [Quarterly agent automation (phases 1-4)](#quarterly-agent-automation-phases-1-4)
- [Optional parallel run](#optional-parallel-run)
- [Inputs and outputs](#inputs-and-outputs)
- [Instrument differences to be aware of](#instrument-differences-to-be-aware-of)
- [Logging and reproducibility](#logging-and-reproducibility)
- [Harmonization consistency review (2026-01-08)](#harmonization-consistency-review-2026-01-08)
- [Contributing](#contributing)

## Repository layout
- `Do-files/` — main Stata pipeline:
  - `00 Master.do` orchestrates the full run.
  - `01_ENOE_Harmonization.do` executes GLD harmonization for each quarter.
  - `02_Append_ENOE_Surveys.do` appends all harmonized quarters, builds panel IDs/flags.
  - `03_Construct_panel_of_workers.do` builds the balanced rotating panel.
  - Label helpers: `ent_mun_label.do`, `lblc_mnpio.do`.
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
- `Output/Quality_Checks/` — generated quality-check outputs by year/quarter.

## Prerequisites
- Stata 16 or newer (tested with Stata MP).
- Sufficient disk for raw ENOE microdata and harmonized outputs.
- Local copies of the ENOE raw/Stata files organized per GLD expectations.

## Quick start
1) Set the base path in `Do-files/00 Master.do` (and any per-user path logic) to your local ENOE data root. Use forward slashes on macOS/Linux.
2) Run from Stata: `do "Do-files/00 Master.do"`.

This will:
- Harmonize each quarter (except 2020.Q2, which is missing).
- Append and construct panel flags/IDs.
- Build the balanced rotating panel.

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
`PANEL/DO/00_Process_ENOE_quarterly_data.do` and `01_Append_ENOE_quarterly_data.do` include parallel run logic that spawns year-specific batch do-files and executes them via `myscript.sh` (macOS) or `.bat` (Windows). Use only if the path/user blocks match your environment.

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

## Logging and reproducibility
- Each step writes a log to `Do-files/Logs/`.
- Quarterly agent run manifests are stored under `Do-files/quarterly_agent/state/`:
  - `state/agent_runs/agent_run_<timestamp>.json`
  - `state/poverty/phase1b_poverty_sync_<timestamp>.json`
  - `state/runs/phase2_run_<year>Q<quarter>_<timestamp>.json`
  - `state/schema/phase4_schema_<year>Q<quarter>_<comparison>_<timestamp>.json` (`comparison` is typically `prev` or `yoy`)
- Scripts assume lowercase variable names after `rename *, lower;`.
- Keep the directory structure intact (GLD format) for relative paths to resolve.
- Harmonization scripts now set `path_in_do` to `\`server'/Do-files` for `ent_mun_label.do`.
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
