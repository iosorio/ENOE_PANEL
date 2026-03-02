# ENOE Quarterly Agent: From Manual Pain to a Reproducible Pipeline

There was one recurring problem: every new ENOE quarter required repeating the same fragile manual steps.

Find new INEGI microdata.  
Download and place ZIP files in the right folder.  
Adjust quarter/year paths.  
Run harmonization and panel scripts.  
Hope nothing changed in the schema.

This folder now contains an agent workflow that automates that process with traceable runs and explicit diagnostics.

Scope note:
- This document describes the `Python+Stata` flow (agent-driven).
- The repository also keeps a `Stata-only` flow via `Do-files/00_Master.do`.
- Consolidated dual-flow guidance is in `ENOE_PANEL/README.md` and `Doc/USAGE.md`.

## What We Have Successfully Built

### Phase 1: INEGI Detection + Download
- Script: `phase1_detect_download.py`
- Detects ENOE microdata releases from INEGI API.
- Resolves quarter/year/variant metadata.
- Downloads ZIPs into quarter-specific `Data/Original`.
- Stores run state in `state/inegi_enoe_phase1_state.json`.

### Phase 1B: INEGI Poverty-Line Sync + Target Scalar Injection
- Script: `phase1b_sync_poverty_lines.py`
- Uses INEGI-only upstreams (LP page/hosted XLSX/ZIP; fallback to INEGI indicator API).
- Builds canonical tables:
  - `Doc/poverty_lines_inegi/poverty_lines_monthly.csv`
  - `Doc/poverty_lines_inegi/poverty_lines_quarterly.csv`
- Patches target harmonization do-file to assign only the active quarter values (`uT\`x'`, `rT\`x'`) from CSV.
- Writes run summaries under `state/poverty/`.

### Phase 2A: Quarter Scaffold
- Script: `phase2_scaffold_quarter.py`
- Creates a new quarter folder from a prior quarter template.
- Updates year/quarter references in harmonization do-files.
- Cleans stale extracted/harmonized outputs in scaffolded folders.

### Phase 2B: Stata Pipeline Execution
- Script: `phase2_run_stata_pipeline.py`
- Extracts raw `.dta` from ZIP into `Data/Stata`.
- Validates required tables (`COE1T`, `COE2T`, `SDEMT`, `HOGT`, `VIVT`).
- Runs harmonization, append, and panel construction.
- Adds `stata_preflight` diagnostics (license/binary/timeout handling).
- Writes structured run summaries under `state/runs/`.

### Phase 2C: Parallel Range Rebuild + OneDrive Safety Gate
- Script: `phase2_rebuild_range_parallel.py`
- Rebuilds a quarter range in parallel using `phase2_run_stata_pipeline.py --skip-append --skip-panel`.
- Runs one final append/panel step after parallel harmonization jobs complete.
- Enforces OneDrive pause acknowledgement before starting (default behavior):
  - ack file: `state/locks/onedrive_paused.ok`
  - run is blocked until ack exists (and is fresh).
- Writes orchestrator summaries under `state/rebuild_parallel/`.

### Future-Proof Output Naming (Implemented)
- `02_Append_ENOE_Surveys.do` and `03_Construct_panel_of_workers.do` now use dynamic panel horizon tags:
  - `MEX_<start>_<endYear>Q<endQ>_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`
  - `MEX_<start>_<endYear>Q<endQ>_PANEL_QUARTER.dta`
- They also publish stable aliases:
  - `MEX_ENOE_V01_M_V06_A_GLD_FULLSAMPLE_latest.dta`
  - `MEX_PANEL_QUARTER_latest.dta`

### Crosswalk Clarification: 4-Digit, 3-Digit, and 2-Digit SCIAN
- ENOE industry source fields (`p4a`, `p7c`) are recorded as 4-digit national codes.
- For 2023+ rounds, metadata points to **SCIAN Hogares 2018**.
- In practice, harmonization uses **3-digit** crosswalk mapping:
  - preferred: `SCIAN_18_3D_ISIC_4.dta`
  - fallback: `SCIAN_07_3D_ISIC_4.dta`
- Why not strict 4-digit matching by default:
  - ENOE includes many 4-digit aggregate/unspecified endings that do not map cleanly at exact 4-digit level.
  - Using 3-digit prefixes keeps coverage stable and comparable over time.
- New fallback now deployed in all harmonization do-files:
  - if 3-digit mapping is missing, code falls back to the 2-digit SCIAN prefix to populate `industrycat10`.
  - example: `6132 -> 61 -> industrycat10 = 10 (Other Services, Unspecified)`.
  - this fallback applies to both primary (`industrycat10`) and secondary (`industrycat10_2`) jobs.
- Important scope:
  - 2-digit fallback assigns broad 1-digit industry groups only;
  - `industrycat_isic` still depends on successful 3-digit SCIAN->ISIC mapping.

### Labor Concept Mapping Hardening (8 Consecutive Quarters)
- We applied a dedicated pass over `2024Q1` to `2025Q4` harmonization do-files to align labor concepts with questionnaire mode.
- Rule now enforced in code:
  - expanded module (`p3j` present): `contract <- p3j`, `union <- p3i`, and `healthins/socialsec <- p3m5/p3m4`;
  - basic module (`p3j` absent): `contract <- p3i`, and union/benefit variables are generated as missing.
- Implementation is variable-driven (`cap confirm variable`) rather than quarter-hardcoded, making future rounds safer when INEGI changes instrument structure.
- Labor cleanup now includes existence guards before replacement, preventing `r(111)` failures on missing module-specific variables.
- Rollout status: same logic propagated for all available rounds from `2005Q1` to `2025Q3` (excluding missing-source quarter `2020Q2` for metadata audit).
- Metadata audit artifact (labels + presence by quarter): `Do-files/quarterly_agent/state/audits/labor_metadata_2005Q1_2025Q3_v2.csv`.

### Phase 4: Schema Diff Intelligence
- Script: `phase4_schema_diff.py`
- Compares schema directly from ZIPs for any selected base/target pair.
- Reports added/removed variables, known rename patterns, type changes.
- Flags potential breaking changes before they silently affect outputs.

### Phase 3: Single Orchestrator Entry Point
- Script: `run_quarterly_agent.py`
- One command that coordinates detection, scaffold, download, poverty sync, schema diff, and pipeline execution.
- Runs two schema checks by default:
  - `schema_prev`: target vs immediately previous quarter.
  - `schema_yoy`: target vs same quarter in prior year.
- Produces an orchestrator run summary in `state/agent_runs/`.

## One-Command Run

From project root:

```bash
python3 ENOE_PANEL/Do-files/quarterly_agent/run_quarterly_agent.py \
  --years 2025 \
  --panel-start-year 2005 \
  --stata-bin stata-mp
```

Notes:
- If no explicit target quarter is passed, the agent chooses the latest quarter detected from INEGI state.
- Add `--dry-run` to validate flow without changing outputs.
- Add `--run-qc` to run QC after panel construction.
- Add `--fail-on-schema-breaking` to stop when either schema check finds breaking changes.
- Add `--skip-poverty-sync` only for troubleshooting; production runs should keep it enabled.

Parallel range example (2021Q1 to 2025Q3):

```bash
touch ENOE_PANEL/Do-files/quarterly_agent/state/locks/onedrive_paused.ok

python3 ENOE_PANEL/Do-files/quarterly_agent/phase2_rebuild_range_parallel.py \
  --start-year 2021 \
  --start-quarter 1 \
  --end-year 2025 \
  --end-quarter 3 \
  --workers 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp
```

Local network Mac example:

```bash
rsync -azP --delete \
  "/Users/israel/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL/" \
  "israel@<REMOTE_IP>:/Users/israel/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL/"

ssh israel@<REMOTE_IP> '
cd "/Users/israel/Library/CloudStorage/OneDrive-Personal/IOR/Projects/Y2025/FY25_MEX_MinimumWage/ENOE_PANEL" &&
touch Do-files/quarterly_agent/state/locks/onedrive_paused.ok &&
python3 Do-files/quarterly_agent/phase2_rebuild_range_parallel.py \
  --start-year 2021 --start-quarter 1 \
  --end-year 2025 --end-quarter 3 \
  --workers 3 \
  --panel-start-year 2005 \
  --stata-bin stata-mp
'
```

## Why This Matters

This is no longer a collection of manual steps.  
It is now an auditable workflow with:
- deterministic commands,
- persistent run state,
- automated poverty-line refresh from INEGI sources,
- explicit error classification,
- schema-change visibility,
- and reproducible panel outputs with quarter tags.

## Current Status

The end-to-end `2025 Q3` pipeline has been successfully executed multiple times with the updated dynamic naming and produced:
- `MEX_2005_2025Q3_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta`
- `MEX_2005_2025Q3_PANEL_QUARTER.dta`
- `*_latest.dta` aliases

The agent is ready for upcoming ENOE harmonization rounds with significantly lower operational risk.
