# Troubleshooting Reference

Use this reference when a run fails or looks suspicious.

## First artifacts to inspect

1. Latest Phase 2 summary JSON in `Do-files/quarterly_agent/state/runs/`
2. Latest agent summary JSON in `Do-files/quarterly_agent/state/agent_runs/`
3. Latest parallel rebuild summary JSON in `Do-files/quarterly_agent/state/rebuild_parallel/`
4. Associated `log_path` or repo-root `tmp_*.log` files

## Common failure classes

### Stata license

Typical signals:
- license expired
- invalid license
- no valid license
- too many users
- all seats in use

### Missing variable / `r(111)`

Typical signals:
- `r(111);`
- `variable ... not found`
- module-specific variables missing in labor cleanup or harmonization blocks

### Path or missing-input failures

Typical signals:
- missing poverty lines CSV
- original directory missing
- ZIP not found for a quarter
- harmonized file missing when append/panel expects it

### Permission failures

Typical signals:
- `Operation not permitted`
- `Permission denied`

### OneDrive gate failures

Typical signals:
- `OneDrive gate not satisfied`
- `missing_ack_file`
- `stale_ack_file`

Remediation:
- pause OneDrive sync,
- refresh the acknowledgment file,
- rerun the parallel rebuild.

## Diagnosis workflow

1. If the artifact is a JSON summary, prefer any existing `diagnostic` payload in the step records.
2. If there is no structured diagnostic, search the text tails and error fields for the known patterns above.
3. Report the most specific category available and point to the exact artifact path.
4. Include the next corrective action, not just the category label.

