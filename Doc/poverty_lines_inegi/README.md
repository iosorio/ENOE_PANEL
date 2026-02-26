# INEGI Poverty Lines (Extreme Income Poverty Line)

This folder stores the canonical poverty-line inputs used by ENOE harmonization.

## Source policy
- Upstream is INEGI only.
- The sync step first tries INEGI-hosted XLSX/ZIP files linked from the LP page.
- If XLSX parsing is unavailable, it falls back to the INEGI indicator API series.

## Files
- `poverty_lines_monthly.csv`: monthly rural/urban values.
- `poverty_lines_quarterly.csv`: quarterly averages (only complete quarters with 3 months).
- `Líneas_de_Pobreza_por_Ingresos_*.xlsx`: optional local snapshots/manual references.

## How data is refreshed
- Script: `Do-files/quarterly_agent/phase1b_sync_poverty_lines.py`
- Standalone example:

```bash
python3 Do-files/quarterly_agent/phase1b_sync_poverty_lines.py \
  --target-year 2025 \
  --target-quarter 3
```

- In orchestrated runs (`run_quarterly_agent.py`), poverty sync runs automatically unless `--skip-poverty-sync` is passed.

## Harmonization integration
- The target quarter do-file is patched to read `poverty_lines_quarterly.csv`.
- It sets only the active quarter scalars:
  - `uT\`x'` (urban)
  - `rT\`x'` (rural)
- If the target quarter row is missing, the do-file exits with an error.
