# ENOE Repository Guide: What We Built and How To Use It

This is a practical guide for new and returning users.

If you remember only one thing, remember this: this repository now supports two valid ways of working.

- `Flow A`: Python + Stata (recommended for repeatable quarterly updates).
- `Flow B`: Stata-only (recommended for users who do not use Python).

Both flows are maintained.

## What Has Been Completed

Over the last implementation rounds, the project moved from manual quarter-by-quarter processing to a reproducible workflow with explicit diagnostics.

Key deliverables completed:

1. ENOE quarter detection/download automation (Phase 1).
2. Poverty-line sync automation from INEGI sources (Phase 1B), with quarter-specific scalar patching.
3. Quarter scaffold tooling for new harmonization rounds (Phase 2A).
4. Stata execution wrapper for harmonization, append, panel, and optional QC (Phase 2B).
5. Parallel rebuild orchestration with OneDrive pause gate (Phase 2C).
6. Dual schema-diff checks:
   - target vs previous quarter;
   - target vs same quarter in prior year.
7. Dynamic fullsample/panel output naming with `latest` aliases.
8. Crosswalk hardening:
   - SCIAN 3-digit primary mapping;
   - 2-digit fallback for broad `industrycat10` assignment.
9. Labor concept mapping hardening across quarters with variable-presence guards.
10. Full-run operational validation through 2025Q3 (including harmonization + panel + QC runs).

## How To Approach This Repository

Use a simple decision rule:

1. If you run quarterly updates and want reproducibility with diagnostics, use `Flow A`.
2. If your team only has Stata, use `Flow B`.

Do not mix entrypoints in the same run session unless you know exactly why.

## Flow A (Python + Stata) in Practice

Use this when your goal is operational reliability and repeatable quarter updates.

Typical entrypoint:

```bash
python3 Do-files/quarterly_agent/run_quarterly_agent.py \
  --years 2025 \
  --target-year 2025 \
  --target-quarter 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp \
  --always-run-pipeline
```

What this gives you:

1. Structured run manifests under `Do-files/quarterly_agent/state/`.
2. Standardized error categories (including Stata runtime/timeout/license signals).
3. Repeatable append/panel output naming (`MEX_<start>_<end>Q<q>_*`) and `latest` aliases.
4. Optional schema and QC integration without changing your Stata harmonization source logic.

Recommended operating pattern:

1. Run with `--dry-run` first when onboarding a machine.
2. Run with real mode for production.
3. Keep one manifest per run and reference it in issue tracking.

## Flow B (Stata-only) in Practice

Use this when users have Stata but no Python workflow.

Entrypoint:

```stata
do "Do-files/00_Master.do"
```

Important:

1. Ensure the `$path` block in `00_Master.do` is correct for your machine.
2. Ensure Step 2 and Step 3 are uncommented if you need append and panel construction.
3. For Stata QChecks, run:

```stata
do "Do-files/Quality_Checks/00_Run_All_Sequential.do"
```

This flow remains fully valid and supported.

## What Was Archived and Why

To reduce clutter without deleting history, we moved deprecated/generated artifacts to:

- `archive_legacy/20260302_094547_dualflow_cleanup/`

Manifest:

- `archive_legacy/20260302_094547_dualflow_cleanup/move_manifest.txt`

This was a non-destructive move. If something is needed again, it can be restored from archive.

## Operational Conventions Going Forward

1. Keep both flows functional in documentation and in code.
2. Prefer adding compatibility guards over hardcoded quarter assumptions.
3. Treat 2020Q2 as an expected missing round.
4. Keep QC outputs and run manifests as first-class evidence for each production run.
5. When changing pipeline behavior, update:
   - `README.md`,
   - `Doc/USAGE.md`,
   - and one blog note in `Do-files/quarterly_agent/`.

## Suggested Onboarding Path for New Users

1. Read `README.md` section `Supported flows`.
2. Choose one flow and run only that flow for your first test.
3. Validate that expected outputs exist in `PANEL/DATA/`.
4. Validate run logs/manifests.
5. Only then move to parallel rebuilds or full historical reruns.

This keeps onboarding fast and avoids most avoidable run failures.

