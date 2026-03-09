# ENOE Panel: Quick Human Guide

This project helps you keep ENOE updated each quarter and produce:

- Harmonized quarter files
- A full stacked ENOE database
- A worker panel dataset

Coverage currently runs from `2005Q1` to `2025Q3`.  
`2020Q2` is expected missing because ENOE source microdata is not available for that quarter.

## Pick One Workflow

Use only one workflow per run:

- `Flow A (Python + Stata)`: best for repeatable quarterly operations and logs.
- `Flow B (Stata-only)`: best when users only have Stata.

## Optional: Codex Skill

If you use Codex in this repo, you can install the operator skill:

```bash
bash codex-skills/install_enoe_skill.sh
```

Then invoke it explicitly as `$enoe-quarterly-agent`.

The skill is for running, rerunning, diagnosing, and explaining the existing ENOE pipeline. It does not replace the underlying Stata/Python code.

## Flow A (Recommended): Python + Stata

Run from repo root:

```bash
python3 Do-files/quarterly_agent/run_quarterly_agent.py \
  --years 2025 \
  --target-year 2025 \
  --target-quarter 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp \
  --always-run-pipeline
```

This flow can do, in order:

1. Find/download the target quarter (when configured)
2. Sync poverty-line values from INEGI sources
3. Run schema checks (`prev` and `yoy`)
4. Run Stata harmonization, append, and panel construction
5. Optionally run QC

Common flags:

- `--dry-run`
- `--run-qc`
- `--fail-on-schema-breaking`
- `--skip-poverty-sync` (debug use only)

## Flow B: Stata-Only

If you do not use Python:

1. Confirm paths in `Do-files/00_Master.do`
2. Keep step 2 and step 3 uncommented in `Do-files/00_Master.do` if you want fullsample + panel outputs
3. Run:

```stata
do "Do-files/00_Master.do"
```

To run Stata QC:

```stata
do "Do-files/Quality_Checks/00_Run_All_Sequential.do"
```

## What You Get

Main outputs:

1. Quarter harmonized file:
`MEX_YYYY_ENOE-QX/.../Data/Harmonized/MEX_YYYY_ENOE_<harm_tag>_ALL.dta`
2. Full sample (dynamic horizon):
`PANEL/DATA/MEX_<start>_<endYear>Q<endQ>_ENOE_<harm_tag>_FULLSAMPLE.dta`
3. Worker panel (dynamic horizon):
`PANEL/DATA/MEX_<start>_<endYear>Q<endQ>_PANEL_QUARTER.dta`
4. Stable aliases for latest run:
`PANEL/DATA/MEX_ENOE_<harm_tag>_FULLSAMPLE_latest.dta`
`PANEL/DATA/MEX_PANEL_QUARTER_latest.dta`

`<harm_tag>` is manifest-driven. The current manifest is `V01_M_V06_A_GLD`, but the pipeline no longer hardcodes that suffix.

## Versioning

The repository now follows an explicit GLD-style versioning policy:

- `V01_M`: raw/master microdata version
- `V06_A`: harmonization template/version
- `GLD`: harmonization acronym

Source of truth:

- `Do-files/00_ENOE_Versioning.do`

Rules:

1. Bump the raw version only when INEGI republishes or changes the raw microdata package.
2. Bump the harmonization version only when the harmonization logic changes enough to define a new reproducible release lineage.
3. Keep the upstream GLD comparison baseline explicit, even if local harmonization moves ahead.

Detailed guidance:

- `Doc/VERSIONING.md`

Upstream GLD comparison:

```bash
python3 Do-files/quarterly_agent/compare_gld_harmonization.py \
  --year 2025 \
  --quarter 3 \
  --fetch-upstream
```

This writes a diff artifact under `Do-files/quarterly_agent/state/upstream_diff/` so local changes can be reviewed and shared with GLD maintainers.

## Optional: Parallel Rebuild (Historical Range)

Use this when rebuilding multiple years:

```bash
touch Do-files/quarterly_agent/state/locks/onedrive_paused.ok
python3 Do-files/quarterly_agent/phase2_rebuild_range_parallel.py \
  --start-year 2021 \
  --start-quarter 1 \
  --end-year 2025 \
  --end-quarter 3 \
  --workers 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp
```

Notes:

- OneDrive pause acknowledgment is enforced by default.
- `2020Q2` is skipped as expected missing input.

## Quality Checks

Canonical Stata QC:

- `Do-files/Quality_Checks/00_Run_All_Sequential.do`
- `Do-files/Quality_Checks/QC_Run_All.do`

Optional Python QC:

- `Do-files/quality_checks_py/qcheck_harmonization.py`

## Folder Map

- `Do-files/`: core Stata pipeline (`00_Master.do`, `01`, `02`, `03`)
- `Do-files/quarterly_agent/`: Python orchestrator and phases
- `MEX_YYYY_ENOE-QX/`: quarter-specific GLD folders
- `PANEL/DATA/`: fullsample and panel outputs
- `Doc/`: source notes and technical docs
- `Output/Quality_Checks/`: QC artifacts
- `archive_legacy/`: archived deprecated/generated clutter

## Important Harmonization Rules

- Industry mapping uses SCIAN 3-digit crosswalk first.
- If 3-digit is unavailable, a 2-digit fallback is used for broad `industrycat10`.
- Labor concept mapping uses variable-presence guards to prevent module-specific `r(111)` errors.

## Logs and Reproducibility

- Stata logs: `Do-files/Logs/`
- Agent manifests: `Do-files/quarterly_agent/state/`

Examples:

- `state/agent_runs/agent_run_<timestamp>.json`
- `state/runs/phase2_run_<year>Q<quarter>_<timestamp>.json`
- `state/rebuild_parallel/phase2_rebuild_parallel_<timestamp>.json`
- `state/schema/phase4_schema_<year>Q<quarter>_<comparison>_<timestamp>.json`

## Deeper Documentation

- `Doc/USAGE.md`
- `Do-files/quarterly_agent/README_BLOG.md`
- `Do-files/quarterly_agent/README_BLOG_02_GUIDE.md`

## Legacy Archive Note

Archived (not deleted) legacy/generated files are in:

- `archive_legacy/20260302_094547_dualflow_cleanup/`
- manifest: `archive_legacy/20260302_094547_dualflow_cleanup/move_manifest.txt`

## Maintainers

When pipeline behavior changes, update:

1. `README.md`
2. `Doc/USAGE.md`
3. At least one note in `Do-files/quarterly_agent/` docs
