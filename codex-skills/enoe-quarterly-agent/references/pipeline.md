# Pipeline Reference

Use this reference for run and rerun tasks.

## Repository validation

Run `scripts/validate_repo.py` first.

Expected repo root contains:
- `Do-files/00_Master.do`
- `Do-files/quarterly_agent/run_quarterly_agent.py`
- `Do-files/quarterly_agent/phase2_rebuild_range_parallel.py`

## Preferred execution order

1. Prefer Python + Stata orchestration for production runs.
2. Use Stata-only only when explicitly requested or when Python orchestration is unavailable.
3. Use dry runs for detection/scaffolding checks when the user wants to inspect the next quarter before a real run.

## Canonical flows

### Quarterly run

Primary runner:
- `Do-files/quarterly_agent/run_quarterly_agent.py`

What it handles:
- quarter detection/download when enabled,
- poverty-line sync,
- schema checks for `prev` and `yoy`,
- Phase 2 Stata harmonization + append + panel,
- optional QC.

Important flags:
- `--target-year`
- `--target-quarter`
- `--panel-start-year`
- `--stata-bin`
- `--dry-run`
- `--run-qc`
- `--skip-download`
- `--skip-scaffold`
- `--skip-poverty-sync`
- `--skip-schema`
- `--always-run-pipeline`

### Parallel rebuild

Primary runner:
- `Do-files/quarterly_agent/phase2_rebuild_range_parallel.py`

Use when rebuilding a historical range, for example `2021Q1` to `2025Q3`.

Important constraints:
- The OneDrive pause gate is enforced by default.
- The acknowledgment file is `Do-files/quarterly_agent/state/locks/onedrive_paused.ok`.
- `2020Q2` is intentionally skipped as a known missing quarter.

### Stata-only

Entrypoint:
- `Do-files/00_Master.do`

Also relevant:
- `Do-files/01_ENOE_Harmonization.do`
- `Do-files/02_Append_ENOE_Surveys.do`
- `Do-files/03_Construct_panel_of_workers.do`

## Outputs

Quarter harmonized file:
- `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_YYYY_ENOE_V01_M_V06_A_GLD_ALL.dta`

Full sample:
- `PANEL/DATA/MEX_<start>_<endYear>Q<endQ>_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`

Worker panel:
- `PANEL/DATA/MEX_<start>_<endYear>Q<endQ>_PANEL_QUARTER.dta`

Latest aliases:
- `PANEL/DATA/MEX_ENOE_V01_M_V06_A_GLD_FULLSAMPLE_latest.dta`
- `PANEL/DATA/MEX_PANEL_QUARTER_latest.dta`

## Logs and state

Primary state locations:
- `Do-files/quarterly_agent/state/agent_runs/`
- `Do-files/quarterly_agent/state/runs/`
- `Do-files/quarterly_agent/state/rebuild_parallel/`
- `Do-files/quarterly_agent/state/schema/`
- `Do-files/quarterly_agent/state/poverty/`

Stata logs can be created in:
- `Do-files/Logs/`
- repo root temporary `tmp_*.log` files produced by wrapper do-files

