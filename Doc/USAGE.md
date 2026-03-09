# ENOE Panel: Usage Guide

This document is the practical companion to the main README.  
It explains how to run the pipeline, what to watch for, and where outputs/logs live.

The repository supports two workflows:

- `Flow A`: Python + Stata (recommended)
- `Flow B`: Stata-only

Coverage in this project is `2005Q1` to `2025Q3`.  
`2020Q2` is expected missing from source data and is skipped by design.

## Optional: Codex Skill

If you work in Codex and want a repo-aware operator layer for this pipeline:

```bash
bash codex-skills/install_enoe_skill.sh
```

Invoke it explicitly as `$enoe-quarterly-agent`.

This skill helps with run orchestration, reruns, QC, diagnosis, and harmonization explanations. It does not add free-form ENOE analytics in this first version.

## Before Running

Check paths in `Do-files/00_Master.do`:

- Set `$path` to your ENOE root folder.
- On macOS/Linux, use forward slashes.
- If there are user/hostname-specific blocks, confirm they match your machine.

Expected quarter folder layout:

- `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_<raw_tag>/Data/Original`
- `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_<raw_tag>/Data/Stata`
- `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_<raw_tag>/Programs`

`<raw_tag>` and `<harm_tag>` are defined in `Do-files/00_ENOE_Versioning.do`.  
The current manifest uses `V01_M` and `V01_M_V06_A_GLD`, but the pipeline now reads those values dynamically.

## Flow A (Recommended): Python + Stata

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

What this runs:

1. Phase 1 quarter detection/download (if enabled)
2. Phase 1B poverty-line sync from INEGI
3. Schema checks (`prev` and `yoy`)
4. Phase 2 Stata harmonization + append + panel
5. Optional QC

Useful flags:

- `--dry-run`
- `--run-qc`
- `--fail-on-schema-breaking`
- `--skip-poverty-sync` (debug only)

## Flow B: Stata-Only

In Stata (16+), run:

```stata
do "Do-files/00_Master.do"
```

Important:

1. `00_Master.do` is the Stata-only entrypoint.
2. Keep step 2 and step 3 uncommented if you want fullsample + panel outputs.
3. Core scripts are:
`01_ENOE_Harmonization.do`, `02_Append_ENOE_Surveys.do`, `03_Construct_panel_of_workers.do`.

Stata logs are written to `Do-files/Logs/`.

## Parallel Options

Python + Stata range rebuild:

- `Do-files/quarterly_agent/phase2_rebuild_range_parallel.py`

Stata QC parallel runner (optional):

- `Do-files/Quality_Checks/00_Run_All_Parallel.do`

## Harmonization Logic You Should Know

- Working hours fields differ by instrument version:
older rounds use `p5c_thrs`/`p5e_thrs`, newer rounds use `p5b_thrs`/`p5d_thrs`.
- Months worked differs across rounds:
older use `p5g*`, newer use `p5f*`.
- Firm size variable differs by quarter:
Q1 often uses `p3q`; Q2-Q4 often use `p3l`.
- Labor concepts depend on questionnaire module:
expanded module usually includes `p3j`, `p3m4`, `p3m5`; basic module does not.
- The pipeline uses variable-presence checks (`cap confirm variable ...`) instead of hardcoded quarter assumptions.
- Geographic code names changed in `2025Q3` (`ent` to `cve_ent`, same pattern for `mun`/`loc`), and are normalized early.
- Weight/strata variable names may differ (`fac_np`/`est_d` vs `fac`/`est_d_tri`), so fallbacks are needed.
- `2020Q2` is a known missing quarter and is skipped by counter logic.

Metadata audit used for this rollout:

- `Do-files/quarterly_agent/state/audits/labor_metadata_2005Q1_2025Q3_v2.csv`

## Industry Crosswalk Policy

Crosswalk source scripts:

- `Doc/Source_Packages/programs/`

Set `ENOE_DOCS` to the folder containing:

- `SCIAN_18_ISIC_4.xlsx`
- `SCIAN_07_ISIC_4.xlsx`
- `tablas_comparativas.xlsx`

Current mapping strategy:

- ENOE source codes (`p4a`/`p7c`) are 4-digit, but harmonization maps first on SCIAN 3-digit keys.
- Preferred crosswalk: `SCIAN_18_3D_ISIC_4.dta`
- Fallback crosswalk: `SCIAN_07_3D_ISIC_4.dta`
- If 3-digit key is unavailable, a 2-digit fallback is used for broad categories (`industrycat10`, `industrycat10_2`).
- `industrycat_isic` may stay missing when no valid 3-digit SCIAN to ISIC mapping exists.

## Shared Helper

Subnational label helper:

- `Do-files/ent_mun_label.do`

Harmonization scripts set `path_in_do` to `` `server'/Do-files `` to reuse this helper consistently.

## Quality Checks

Canonical Stata QC:

- `Do-files/Quality_Checks/00_Run_All_Sequential.do`
- `Do-files/Quality_Checks/QC_Run_All.do`
- Optional parallel: `Do-files/Quality_Checks/00_Run_All_Parallel.do`
- Output path: `Output/Quality_Checks/by-year/YYYY/QX/`

Python QC runner:

- `Do-files/quality_checks_py/qcheck_harmonization.py`

Single dataset:

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --dataset <harmonized_dta> \
  --reports static,basic,categoric \
  --profile full
```

Batch run:

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --batch \
  --start-year 2005 \
  --end-year 2025 \
  --reports static,basic,categoric \
  --profile full
```

Python QC output path:

- `Output/Quality_Checks_Py/by-year/YYYY/QX/`

## Outputs

- Harmonized quarter files under each quarter’s `Data/Harmonized/`
- Full appended sample:
`PANEL/DATA/MEX_<start>_<end>Q<q>_ENOE_<harm_tag>_FULLSAMPLE.dta`
- Worker panel:
`PANEL/DATA/MEX_<start>_<end>Q<q>_PANEL_QUARTER.dta`
- Stable latest aliases:
`PANEL/DATA/MEX_ENOE_<harm_tag>_FULLSAMPLE_latest.dta`
`PANEL/DATA/MEX_PANEL_QUARTER_latest.dta`

Current full-window naming in this project: `MEX_2005_2025Q3_*`  
Excel outputs are not generated by the current pipeline.

## Versioning and GLD Comparison

Versioning source of truth:

- `Do-files/00_ENOE_Versioning.do`

Detailed policy:

- `Doc/VERSIONING.md`

Operational rules:

1. Bump `V##_M` only when INEGI changes the raw microdata lineage.
2. Bump `V##_A` only when the harmonization logic changes substantially.
3. Keep the upstream GLD comparison baseline explicit so local-vs-upstream diffs are reproducible.

To sync historical quarter do-file headers with their file names:

```bash
python3 Do-files/quarterly_agent/sync_harmonization_versions.py
```

To compare a local quarter do-file against upstream World Bank GLD:

```bash
python3 Do-files/quarterly_agent/compare_gld_harmonization.py \
  --year 2025 \
  --quarter 3 \
  --fetch-upstream
```

The diff patch and JSON summary are written under `Do-files/quarterly_agent/state/upstream_diff/`.

## Troubleshooting

- Missing variable errors (`p5b_thrs`, `p5f1`, `ent`, etc.):
use `cap confirm var` branches and normalize names early.
- Path errors:
verify `$path` in `Do-files/00_Master.do` and folder layout.
- `2020Q2` handling:
expected missing; marked as skipped.
- Stata failures:
Phase 2 wrapper treats runtime `r(<code>)` log errors as failures even when process exit code is zero.

## Legacy Archive

Deprecated/generated clutter was moved (not deleted) to:

- `archive_legacy/20260302_094547_dualflow_cleanup/`

Manifest:

- `archive_legacy/20260302_094547_dualflow_cleanup/move_manifest.txt`
