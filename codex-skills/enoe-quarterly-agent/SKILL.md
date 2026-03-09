---
name: enoe-quarterly-agent
description: Use this skill when working in the ENOE_PANEL repository to run or rerun quarterly ENOE harmonization, append/panel builds, QC, diagnose Stata or pipeline failures, or answer harmonization questions about education, industry, labor cleanup, poverty lines, and schema changes.
---

# ENOE Quarterly Agent

## Overview

This skill turns Codex into an operator for the ENOE quarterly pipeline.

Use it to:
- run or rerun quarter processing,
- rebuild historical ranges,
- run Stata or Python quality checks,
- rerun quarter-only QC against an existing harmonized file,
- diagnose failed Stata or orchestration runs, and
- explain how the current harmonization works.

This skill is explicit-only. Invoke it as `$enoe-quarterly-agent`.

## Workflow

1. Validate the repository first with `scripts/validate_repo.py`.
2. For execution tasks, prefer the Python + Stata flow and build commands with `scripts/build_command.py`.
3. Use Stata-only commands only when the user explicitly asks for them or Python orchestration is unavailable.
4. For quarter-only QC reruns, prefer the wrapper scripts:
   - `Do-files/quarterly_agent/run_qc_only.sh`
   - `Do-files/quarterly_agent/run_qc_stata_sequential.sh`
5. For diagnosis, run `scripts/diagnose_stata_failure.py` on a provided artifact or let it inspect the latest run artifact.
6. For explanation tasks, read the repo docs first, then inspect the authoritative do-file or runner that implements the behavior.

## Guardrails

- Keep the real pipeline in the repo. Do not duplicate harmonization logic inside the skill.
- Surface repo-specific constraints in answers:
  - coverage currently runs through `2025Q4`,
  - `2020Q2` is expected missing,
  - parallel rebuilds require the OneDrive pause acknowledgment file,
  - schema checks compare both `prev` and `yoy`,
  - poverty-line inputs come from the INEGI CSV sync,
  - `--run-qc` defaults to quarter-scoped Python QC, while the old repo-wide Stata QC is explicit via `stata-sequential`.
- For quarter-specific harmonization answers, inspect the actual quarter do-file under `MEX_YYYY_ENOE-QX/.../Programs/`.
- For free-form ENOE analytics requests such as LFP or educational attainment estimates, explain that this v1 skill does not compute survey statistics.

## References

- For execution flows and outputs: `references/pipeline.md`
- For harmonization logic: `references/harmonization.md`
- For quality checks: `references/qchecks.md`
- For failure diagnosis patterns: `references/troubleshooting.md`
