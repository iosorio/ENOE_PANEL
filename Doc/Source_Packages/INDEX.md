# Source Packages Index

Canonical R scripts for building classification crosswalks used in the ENOE harmonization.

## Quick start
Set `ENOE_DOCS` to the folder containing:
- `SCIAN_18_ISIC_4.xlsx`
- `SCIAN_07_ISIC_4.xlsx`
- `tablas_comparativas.xlsx`

Then run a script with R, for example:
```bash
Rscript Doc/Source_Packages/programs/naics_to_isic_correspondance.R
```

## Canonical programs
- `programs/naics_to_isic_correspondance.R` - Builds SCIAN (2018) -> ISIC Rev.4 crosswalk from `SCIAN_18_ISIC_4.xlsx`.
- `programs/SCIAN_07_3D_ISIC_4.R` - Builds 3-digit SCIAN (2007) -> ISIC Rev.4 concordance from `SCIAN_07_ISIC_4.xlsx`.
- `programs/sinco_to_isco_correspondance.R` - Builds SINCO -> ISCO crosswalk from `tablas_comparativas.xlsx`.
- `programs/cmo_isco_via_sinco.R` - Builds CMO -> ISCO via SINCO from `tablas_comparativas.xlsx`.

## Notes
- Outputs are written to the same folder as the inputs (the `ENOE_DOCS` path) as `.dta` files.
- These scripts were consolidated from per-quarter copies; only canonical versions remain.
