# Python Harmonization Quality Checks (qcheck-style)

This folder provides a Python quality-check pipeline modeled on the `worldbank/qcheck` workflow:

- `static`: rule-based consistency checks.
- `basic`: descriptive statistics for numeric variables.
- `categoric`: category shares for low-cardinality variables.

Main runner:
- `qcheck_harmonization.py`

## Why this exists

The current canonical QC is implemented in Stata under `Do-files/Quality_Checks/`. This Python runner mirrors the same logic/procedures with:

- reproducible CLI execution,
- configurable check scope (`core` vs `full`),
- optional custom expression rules (`--custom-rules`), and
- batch execution across quarters.

## Quick start

Run one harmonized file:

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --dataset MEX_2025_ENOE-Q3/MEX_2025_ENOE_<harm_tag>/Data/Harmonized/MEX_2025_ENOE_<harm_tag>_ALL.dta \
  --reports static,basic,categoric \
  --profile full \
  --xlsx
```

`<harm_tag>` comes from `Do-files/00_ENOE_Versioning.do`. The current local manifest value is `V01_M_V07_A_GLD`; the upstream GLD comparison baseline remains `V01_M_V06_A_GLD`.

Run all available quarters (2005-2025):

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --batch \
  --start-year 2005 \
  --end-year 2025 \
  --reports static,basic,categoric \
  --profile full
```

## Outputs

Outputs are written to `Output/Quality_Checks_Py/` by default.

For each quarter, files are produced under:

- `Output/Quality_Checks_Py/by-year/YYYY/QX/`

Artifacts per survey:

- `*_qcheck_static_py.csv`
- `*_qcheck_basic_py.csv`
- `*_qcheck_categoric_py.csv`
- `*_qcheck_py.xlsx` (when `--xlsx` is used)

Run summary:

- `Output/Quality_Checks_Py/run_summary.json`

## QC triage (short guide)
Use this order when reviewing results:

1. `severity = 1` rows first (must-fix).
2. Then warning-level rows (for example expected all-missing/invariant warnings).
3. Prioritize by `failed_ratio` and then `failed_n`.
4. Start with `Overall` and `Survey & ID`, then `Geography/Demography`, then `Labour`.
5. Suggested thresholds on critical variables:
   - `failed_ratio > 5%`: block release.
   - `0.5% to 5%`: fix before final panel if possible.
   - `<0.5%`: targeted review and document if accepted.

## Static checks covered

The static report uses `Do-files/Quality_Checks/helpers/Helper_GLD_VarLists.do` as the source of truth and implements checks aligned with the GLD/qcheck logic, including:

- dictionary presence and unexpected variables,
- type checks, all-missing checks,
- invariant / should-vary checks,
- household-level consistency,
- categorical range checks,
- survey/version/ID checks,
- demography, migration, education, training checks,
- labour checks (in `--profile full`), including skip patterns, wage consistency, hours consistency, ISIC/ISCO format and universe checks, and wage-unit pair consistency.

## Custom rules (optional)

You can append custom checks with JSON expressions:

```bash
python Do-files/quality_checks_py/qcheck_harmonization.py \
  --dataset <path-to-dta> \
  --custom-rules Do-files/quality_checks_py/custom_rules.example.json
```

Expression fields are evaluated with `pandas.DataFrame.eval`.
