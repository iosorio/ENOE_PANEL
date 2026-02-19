# Quality Checks

Canonical GLD quality check scripts for ENOE harmonization. These checks can run sequentially or in parallel and write outputs to `Output/Quality_Checks/`.

## Structure
- `helpers/` — shared helper programs and reference files used by the checks.
- `QC_Run_All.do` — parameterized runner for a single quarter.
- `00_Run_All_Sequential.do` — runs all quarters sequentially (skips 2020.Q2).
- `00_Run_All_Parallel.do` — creates year-specific batch files and runs in parallel (optional).

## Outputs
- Generated files are written to `Output/Quality_Checks/by-year/YYYY/QX/`.

## Helper references
- `helpers/isic_codes.txt` and `helpers/isco_codes.txt` are reference code lists.
- `helpers/create_isic_isco_txt.R` and `helpers/Dynamic Quality Checks.R` are upstream helper scripts.

## Usage
Sequential:
```stata
do "Do-files/Quality_Checks/00_Run_All_Sequential.do"
```

Parallel (macOS):
```stata
do "Do-files/Quality_Checks/00_Run_All_Parallel.do"
```
