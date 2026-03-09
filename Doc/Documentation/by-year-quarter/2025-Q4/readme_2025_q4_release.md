# ENOE 2025-Q4 Release Note

## Official source

- INEGI download record detected by the quarterly agent on `2026-03-09`.
- API/source id: `3233701`
- Title: `Programas|Encuesta Nacional de Ocupación y Empleo (ENOE), población de 15 años y más de edad|Base de datos|IV Trimestre (ENOE)`
- Official download URL:
  `https://www.inegi.org.mx/contenidos/programas/enoe/15ymas/microdatos/enoe_2025_trim4_dta.zip`
- Reported size label from INEGI API: `61.2 MB`

## Raw schema result

Raw schema checks were run with the dual comparison policy:

1. `prev`: `2025-Q4` vs `2025-Q3`
2. `yoy`: `2025-Q4` vs `2024-Q4`

Artifacts:

- `Do-files/quarterly_agent/state/schema/phase4_schema_2025Q4_prev_20260309T160732Z.json`
- `Do-files/quarterly_agent/state/schema/phase4_schema_2025Q4_prev_20260309T160732Z.md`
- `Do-files/quarterly_agent/state/schema/phase4_schema_2025Q4_yoy_20260309T160735Z.json`
- `Do-files/quarterly_agent/state/schema/phase4_schema_2025Q4_yoy_20260309T160735Z.md`

Summary:

- `2025-Q4` vs `2025-Q3`: `ok`
- No added, removed, or type-changed variables in `COE1T`, `COE2T`, `SDEMT`, `HOGT`, or `VIVT`.
- `2025-Q4` vs `2024-Q4`: `changed`
- The year-on-year differences are the same geography renames/additions already introduced in the `2025` redesign cycle:
  - `ENT -> CVE_ENT`
  - `MUN -> CVE_MUN`
  - `LOC -> CVE_LOC`
  - `AGEB -> CVE_AGEB`
  - new `CVEGEO`
- Conclusion: no new quarter-specific structural break was introduced in `2025-Q4` relative to `2025-Q3`.

## Local workflow fixes required

The raw release itself was not the problem. The local workflow needed four fixes:

1. `Do-files/quarterly_agent/phase2_scaffold_quarter.py`
   - fixed the auto-source quarter helper call (`quarter_root(...)`) so scaffold can resolve the previous quarter correctly.
2. `Do-files/quarterly_agent/phase2_scaffold_quarter.py`
   - preserved a newly downloaded target ZIP when `--force` is used on an existing quarter root.
3. `MEX_2025_ENOE-Q4/MEX_2025_ENOE_V01_M_V07_A_GLD/Programs/MEX_2025_ENOE_V01_M_V07_A_GLD_ALL.do`
   - replaced the hardcoded `use_enoe` quarter list with a year-based regime rule so `2025-Q4` (`x = 425`) uses the `ENOE_*.dta` branch.
4. `Do-files/00_ENOE_Versioning.do`
   - shortened the upstream comparison global names to stay within Stata's name-length limit.

## Rebuilt outputs

Quarter harmonized file:

- `MEX_2025_ENOE-Q4/MEX_2025_ENOE_V01_M_V07_A_GLD/Data/Harmonized/MEX_2025_ENOE_V01_M_V07_A_GLD_ALL.dta`

Full sample:

- `PANEL/DATA/MEX_2005_2025Q4_ENOE_V01_M_V07_A_GLD_FULLSAMPLE.dta`
- `PANEL/DATA/MEX_ENOE_V01_M_V07_A_GLD_FULLSAMPLE_latest.dta`

Worker panel:

- `PANEL/DATA/MEX_2005_2025Q4_PANEL_QUARTER.dta`
- `PANEL/DATA/MEX_PANEL_QUARTER_latest.dta`

## Quarter-scoped QC

The canonical Stata sequential QC wrapper is repo-wide and was not used as the final validation artifact for this release note.
Instead, a targeted Python qcheck was run for the `2025-Q4` harmonized dataset.

Artifacts:

- `Output/Quality_Checks_Py/single/MEX_2025_ENOE_V01_M_V07_A_GLD_ALL_qcheck_static_py.csv`
- `Output/Quality_Checks_Py/single/MEX_2025_ENOE_V01_M_V07_A_GLD_ALL_qcheck_basic_py.csv`
- `Output/Quality_Checks_Py/single/MEX_2025_ENOE_V01_M_V07_A_GLD_ALL_qcheck_categoric_py.csv`
- `Output/Quality_Checks_Py/single/MEX_2025_ENOE_V01_M_V07_A_GLD_ALL_qcheck_py.xlsx`

Row counts:

- static: `159`
- basic: `3360`
- categoric: `632`

Main non-zero severity `1` rows in the static report:

- `industrycat_isic`, `industrycat_isic_2`, `occup_isco`, `occup_isco_2`: labour answers present for some `7-day NLF` cases (`147,319` rows) and some `7-day unemployed` cases (`5,462` rows)
- `t_hours_annual`, `t_hours_total`: values outside expected range `1..3120` (`7,877` rows)
- `whours`: values outside expected range `1..84` (`3,156` rows)
- `nlfreason`: partial missingness among some NLF cases (`30` rows)

These are content/QC review items, not a quarter-to-quarter schema break.
