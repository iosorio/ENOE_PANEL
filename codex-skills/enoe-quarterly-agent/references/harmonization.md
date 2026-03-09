# Harmonization Reference

Use this reference when explaining how variables are harmonized.

## Authoritative sources

Start with:
- `README.md`
- `Doc/USAGE.md`

For quarter-specific behavior, inspect:
- `MEX_YYYY_ENOE-QX/MEX_YYYY_ENOE_V01_M_V06_A_GLD/Programs/MEX_YYYY_ENOE_V01_M_V06_A_GLD_ALL.do`

## Education

Key outputs:
- `educy`
- `educat7`
- `educat5`
- `educat4`
- `educat_isced`
- `isced_version`

Current logic:
- education years and categorical attainment are generated from the ENOE schooling variables in the quarter do-file,
- `educat_isced` uses `isced_2011`,
- quality checks enforce the hierarchy between `educat4`, `educat5`, and `educat7`.

When the user asks how education is harmonized:
1. inspect the current quarter do-file around the `educy` and `educat*` blocks,
2. confirm the `isced_version`,
3. mention the QC hierarchy checks if relevant.

## Industry

Key outputs:
- `industry_orig`
- `industrycat_isic`
- `industrycat10`
- `industrycat10_2`

Current logic:
- map ENOE source codes through SCIAN 3-digit keys first,
- use a 2-digit fallback for broad `industrycat10` assignments when 3-digit mapping is unavailable,
- quarter-specific do-files may document the SCIAN definition in labels and headers.

Important limitation:
- `industrycat_isic` can remain missing when no valid 3-digit SCIAN to ISIC mapping exists.

## Labor cleanup and questionnaire shifts

The pipeline handles instrument drift defensively:
- working-hours fields vary across rounds,
- months-worked fields vary across rounds,
- firm-size variables vary by quarter,
- expanded vs basic questionnaire modules change which labor concept variables are present.

Current policy:
- use variable-presence checks instead of quarter-only assumptions,
- guard labor cleanup loops so absent module-specific variables do not trigger `r(111)`.

## Poverty lines

The poverty-line logic is dynamic, not hardcoded.

Current source:
- `Doc/poverty_lines_inegi/poverty_lines_quarterly.csv`

Current behavior:
- the quarterly agent syncs poverty lines from INEGI sources,
- the harmonization do-file loads the CSV,
- only the row for the current year and quarter is used to set the poverty-line scalars.

When a user asks about poverty-line logic, mention that the historical hardcoded scalar block was replaced by the CSV-driven quarterly lookup.

## Schema checks

The pipeline runs two schema comparisons:
- `prev`: current quarter vs previous quarter
- `yoy`: current quarter vs same quarter in the previous year

When the user asks about a recent schema change, inspect the latest schema state files under `Do-files/quarterly_agent/state/schema/`.

