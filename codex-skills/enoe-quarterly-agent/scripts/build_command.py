#!/usr/bin/env python3
"""Build canonical ENOE pipeline commands without executing them."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from validate_repo import resolve_repo_root


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Build ENOE pipeline commands")
    ap.add_argument("--cwd", default=None, help="Starting directory for repo discovery")
    ap.add_argument("--repo-root", default=None, help="Explicit ENOE_PANEL repo root override")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")

    sub = ap.add_subparsers(dest="task", required=True)

    qrun = sub.add_parser("quarterly-run", help="Build run_quarterly_agent.py command")
    qrun.add_argument("--year", type=int, required=True)
    qrun.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], required=True)
    qrun.add_argument("--years", default=None)
    qrun.add_argument("--panel-start-year", type=int, default=2005)
    qrun.add_argument("--stata-bin", default="stata-mp")
    qrun.add_argument("--timeout-seconds", type=int, default=4 * 60 * 60)
    qrun.add_argument("--run-qc", action="store_true")
    qrun.add_argument("--dry-run", action="store_true")
    qrun.add_argument("--overwrite-download", action="store_true")
    qrun.add_argument("--force-scaffold", action="store_true")
    qrun.add_argument("--skip-detect", action="store_true")
    qrun.add_argument("--skip-download", action="store_true")
    qrun.add_argument("--skip-scaffold", action="store_true")
    qrun.add_argument("--skip-poverty-sync", action="store_true")
    qrun.add_argument("--skip-schema", action="store_true")
    qrun.add_argument("--skip-pipeline", action="store_true")
    qrun.add_argument("--always-run-pipeline", action="store_true")
    qrun.add_argument("--fail-on-schema-breaking", action="store_true")
    qrun.add_argument("--verbose", action="store_true")

    rebuild = sub.add_parser("parallel-rebuild", help="Build parallel rebuild command")
    rebuild.add_argument("--start-year", type=int, required=True)
    rebuild.add_argument("--start-quarter", type=int, choices=[1, 2, 3, 4], default=1)
    rebuild.add_argument("--end-year", type=int, required=True)
    rebuild.add_argument("--end-quarter", type=int, choices=[1, 2, 3, 4], default=4)
    rebuild.add_argument("--workers", type=int, default=2)
    rebuild.add_argument("--panel-start-year", type=int, default=2005)
    rebuild.add_argument("--stata-bin", default="stata-mp")
    rebuild.add_argument("--timeout-seconds", type=int, default=4 * 60 * 60)
    rebuild.add_argument("--skip-extract", action="store_true")
    rebuild.add_argument("--skip-finalize", action="store_true")
    rebuild.add_argument("--finalize-skip-extract", action=argparse.BooleanOptionalAction, default=True)
    rebuild.add_argument("--run-qc", action="store_true")
    rebuild.add_argument("--continue-on-error", action="store_true")
    rebuild.add_argument("--dry-run", action="store_true")
    rebuild.add_argument("--verbose", action="store_true")
    rebuild.add_argument("--require-onedrive-paused", action=argparse.BooleanOptionalAction, default=True)
    rebuild.add_argument("--wait-for-onedrive", action="store_true")
    rebuild.add_argument("--wait-timeout-seconds", type=int, default=3600)
    rebuild.add_argument("--poll-seconds", type=int, default=15)

    master = sub.add_parser("stata-master", help="Build Stata-only master command")
    master.add_argument("--stata-bin", default="stata-mp")

    stata_qc = sub.add_parser("stata-qc", help="Build Stata QC command")
    stata_qc.add_argument("--stata-bin", default="stata-mp")
    stata_qc.add_argument("--parallel", action="store_true")

    py_qc = sub.add_parser("python-qc", help="Build Python QC command")
    py_qc.add_argument("--dataset", default=None)
    py_qc.add_argument("--batch", action="store_true")
    py_qc.add_argument("--start-year", type=int, default=2005)
    py_qc.add_argument("--end-year", type=int, default=2025)
    py_qc.add_argument("--quarters", default="1,2,3,4")
    py_qc.add_argument("--include-2020q2", action="store_true")
    py_qc.add_argument("--reports", default="static,basic,categoric")
    py_qc.add_argument("--profile", choices=["core", "full"], default="full")
    py_qc.add_argument("--xlsx", action="store_true")
    py_qc.add_argument("--strict", action="store_true")
    return ap.parse_args()


def require_repo_root(args: argparse.Namespace) -> Path:
    repo_root, payload = resolve_repo_root(args.cwd, args.repo_root)
    if repo_root is None:
        print(json.dumps(payload, ensure_ascii=True, indent=2), file=sys.stderr)
        raise SystemExit(2)
    return repo_root


def append_flag(cmd: list[str], enabled: bool, flag: str) -> None:
    if enabled:
        cmd.append(flag)


def build_quarterly_run(args: argparse.Namespace, repo_root: Path) -> tuple[list[str], list[str]]:
    cmd = [
        "python3",
        "Do-files/quarterly_agent/run_quarterly_agent.py",
        "--repo-root",
        str(repo_root),
        "--target-year",
        str(args.year),
        "--target-quarter",
        str(args.quarter),
        "--panel-start-year",
        str(args.panel_start_year),
        "--stata-bin",
        args.stata_bin,
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.years:
        cmd.extend(["--years", args.years])
    append_flag(cmd, args.run_qc, "--run-qc")
    append_flag(cmd, args.dry_run, "--dry-run")
    append_flag(cmd, args.overwrite_download, "--overwrite-download")
    append_flag(cmd, args.force_scaffold, "--force-scaffold")
    append_flag(cmd, args.skip_detect, "--skip-detect")
    append_flag(cmd, args.skip_download, "--skip-download")
    append_flag(cmd, args.skip_scaffold, "--skip-scaffold")
    append_flag(cmd, args.skip_poverty_sync, "--skip-poverty-sync")
    append_flag(cmd, args.skip_schema, "--skip-schema")
    append_flag(cmd, args.skip_pipeline, "--skip-pipeline")
    append_flag(cmd, args.always_run_pipeline, "--always-run-pipeline")
    append_flag(cmd, args.fail_on_schema_breaking, "--fail-on-schema-breaking")
    append_flag(cmd, args.verbose, "--verbose")
    notes = [
        "Preferred flow for real quarterly operations.",
        "If running a historical rerun against existing inputs, combine --skip-download with --always-run-pipeline as needed.",
    ]
    return cmd, notes


def build_parallel_rebuild(args: argparse.Namespace, repo_root: Path) -> tuple[list[str], list[str]]:
    cmd = [
        "python3",
        "Do-files/quarterly_agent/phase2_rebuild_range_parallel.py",
        "--repo-root",
        str(repo_root),
        "--start-year",
        str(args.start_year),
        "--start-quarter",
        str(args.start_quarter),
        "--end-year",
        str(args.end_year),
        "--end-quarter",
        str(args.end_quarter),
        "--workers",
        str(args.workers),
        "--panel-start-year",
        str(args.panel_start_year),
        "--stata-bin",
        args.stata_bin,
        "--timeout-seconds",
        str(args.timeout_seconds),
        f"--{'require-onedrive-paused' if args.require_onedrive_paused else 'no-require-onedrive-paused'}",
        f"--{'finalize-skip-extract' if args.finalize_skip_extract else 'no-finalize-skip-extract'}",
        "--wait-timeout-seconds",
        str(args.wait_timeout_seconds),
        "--poll-seconds",
        str(args.poll_seconds),
    ]
    append_flag(cmd, args.skip_extract, "--skip-extract")
    append_flag(cmd, args.skip_finalize, "--skip-finalize")
    append_flag(cmd, args.run_qc, "--run-qc")
    append_flag(cmd, args.continue_on_error, "--continue-on-error")
    append_flag(cmd, args.dry_run, "--dry-run")
    append_flag(cmd, args.verbose, "--verbose")
    append_flag(cmd, args.wait_for_onedrive, "--wait-for-onedrive")
    notes = [
        "Parallel rebuild enforces the OneDrive pause gate by default.",
        "The acknowledgment file is Do-files/quarterly_agent/state/locks/onedrive_paused.ok.",
        "2020Q2 is expected missing and will be skipped by the runner.",
    ]
    return cmd, notes


def build_stata_master(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    return [args.stata_bin, "-b", "do", "Do-files/00_Master.do"], [
        "Stata-only flow.",
        "Make sure append/panel steps remain uncommented in Do-files/00_Master.do when full outputs are required.",
    ]


def build_stata_qc(args: argparse.Namespace) -> tuple[list[str], list[str]]:
    do_file = "Do-files/Quality_Checks/00_Run_All_Parallel.do" if args.parallel else "Do-files/Quality_Checks/00_Run_All_Sequential.do"
    return [args.stata_bin, "-b", "do", do_file], [
        "Stata is the canonical QC implementation for this repo.",
    ]


def build_python_qc(args: argparse.Namespace, repo_root: Path) -> tuple[list[str], list[str]]:
    if bool(args.dataset) == bool(args.batch):
        raise SystemExit("python-qc requires exactly one of --dataset or --batch")

    cmd = [
        "python3",
        "Do-files/quality_checks_py/qcheck_harmonization.py",
        "--repo-root",
        str(repo_root),
        "--reports",
        args.reports,
        "--profile",
        args.profile,
    ]
    if args.dataset:
        cmd.extend(["--dataset", args.dataset])
    else:
        cmd.extend(
            [
                "--batch",
                "--start-year",
                str(args.start_year),
                "--end-year",
                str(args.end_year),
                "--quarters",
                args.quarters,
            ]
        )
        append_flag(cmd, args.include_2020q2, "--include-2020q2")
    append_flag(cmd, args.xlsx, "--xlsx")
    append_flag(cmd, args.strict, "--strict")
    return cmd, [
        "Python QC mirrors the canonical Stata logic and writes CSV/XLSX artifacts under Output/Quality_Checks_Py.",
    ]


def build_payload(args: argparse.Namespace) -> dict[str, object]:
    repo_root = require_repo_root(args)
    builders = {
        "quarterly-run": lambda: build_quarterly_run(args, repo_root),
        "parallel-rebuild": lambda: build_parallel_rebuild(args, repo_root),
        "stata-master": lambda: build_stata_master(args),
        "stata-qc": lambda: build_stata_qc(args),
        "python-qc": lambda: build_python_qc(args, repo_root),
    }
    cmd, notes = builders[args.task]()
    return {
        "status": "ok",
        "task": args.task,
        "repo_root": str(repo_root),
        "cwd": str(repo_root),
        "cmd": cmd,
        "shell_string": shlex.join(cmd),
        "notes": notes,
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    indent = 2 if args.pretty else None
    print(json.dumps(payload, ensure_ascii=True, indent=indent))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

