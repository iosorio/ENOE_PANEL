# Quality Checks Reference

Use this reference for QC run selection, outputs, and triage.

## Canonical QC

Stata remains the canonical QC implementation:
- `Do-files/Quality_Checks/00_Run_All_Sequential.do`
- `Do-files/Quality_Checks/QC_Run_All.do`

Optional Stata parallel runner:
- `Do-files/Quality_Checks/00_Run_All_Parallel.do`

Python mirror:
- `Do-files/quality_checks_py/qcheck_harmonization.py`

## When to use which runner

- Use Stata QC when the user wants the canonical GLD-style results.
- Use Python QC when the user wants reproducible CLI output, batch runs, or CSV/XLSX artifacts without relying on Stata QC output formats.
- For a single harmonized quarter after rerunning Phase 2, use a targeted QC run rather than the whole historical range unless the user asks for the full range.

## Output locations

Stata QC outputs:
- `Output/Quality_Checks/by-year/YYYY/QX/`

Python QC outputs:
- `Output/Quality_Checks_Py/by-year/YYYY/QX/`
- `Output/Quality_Checks_Py/run_summary.json`

## Short triage guide

Prioritize review in this order:
1. `severity = 1` rows first,
2. then warning-level rows,
3. then sort by `failed_ratio`,
4. then sort by `failed_n`.

Suggested triage thresholds for critical variables:
- `failed_ratio > 5%`: block release
- `0.5% to 5%`: fix before final panel if possible
- `< 0.5%`: targeted review and document if accepted

Common starting points:
- `Overall`
- `Survey & ID`
- `Geography/Demography`
- `Labour`

## Structural false positives

This repo already suppresses some structural false positives in QC.

When reviewing flags:
- check whether the issue reflects a real harmonization defect,
- compare against questionnaire/module differences,
- inspect crosswalk-driven variables separately from direct recodes,
- do not treat expected WDI no-data flags as harmonization failures.

