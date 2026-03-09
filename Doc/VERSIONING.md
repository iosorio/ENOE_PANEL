# ENOE Versioning

This repo follows the World Bank GLD naming pattern:

- `MEX`: country code
- `2005`: survey year
- `ENOE`: survey name
- `V01_M`: raw/master data version
- `V06_A`: harmonization version
- `GLD`: harmonization template acronym

Example:

- `MEX_2005_ENOE_V01_M_V06_A_GLD`

## Versioning rules

1. Bump the raw/master version only when INEGI republishes or changes the raw microdata package in a way that changes the master input lineage.
2. Bump the harmonization version only when the harmonization logic/template changes substantially enough to justify a new reproducible release lineage.
3. Keep the local current version separate from the upstream GLD comparison baseline. This matters when local work advances beyond the upstream GLD release.

## Source of truth

The repo-wide version manifest is:

- `Do-files/00_ENOE_Versioning.do`

Both Stata and Python utilities should read from that manifest instead of hardcoding `V01_M_V06_A_GLD`.

## Keeping do-files consistent

Use:

```bash
python3 Do-files/quarterly_agent/sync_harmonization_versions.py
```

This synchronizes harmonization do-file headers and local version tokens with their file names.

## Comparing local code against upstream GLD

Use:

```bash
python3 Do-files/quarterly_agent/compare_gld_harmonization.py \
  --year 2025 \
  --quarter 3 \
  --fetch-upstream
```

Behavior:

1. Clones or refreshes `worldbank/gld` into a temp folder.
2. Resolves the local quarter do-file using the current repo version manifest.
3. Resolves the upstream GLD do-file using the configured upstream comparison baseline.
   If the requested survey year does not exist upstream at that baseline, the tool falls back to the latest available upstream year for the same baseline and records that decision in the JSON summary.
4. Writes a unified diff patch and JSON summary under:
   `Do-files/quarterly_agent/state/upstream_diff/`

Recommended review practice:

1. Compare one local quarter at a time against the upstream GLD year/version do-file.
2. Keep the diff patch as the artifact to share with GLD maintainers.
3. When changes are accepted upstream, update the upstream comparison baseline if needed.
