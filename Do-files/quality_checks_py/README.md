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
  --dataset MEX_2025_ENOE-Q3/MEX_2025_ENOE_V01_M_V06_A_GLD/Data/Harmonized/MEX_2025_ENOE_V01_M_V06_A_GLD_ALL.dta \
  --reports static,basic,categoric \
  --profile full \
  --xlsx
```

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

