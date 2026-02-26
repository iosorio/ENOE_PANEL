#!/usr/bin/env python3
"""Phase 3: end-to-end quarterly ENOE agent orchestrator."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_out_dir = default_repo / "Do-files" / "quarterly_agent" / "state" / "agent_runs"

    now = dt.datetime.now()
    default_years = f"{now.year-1},{now.year}"

    ap = argparse.ArgumentParser(description="Run ENOE quarterly agent end-to-end")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--years", default=default_years, help="Comma-separated years for INEGI detection")
    ap.add_argument("--target-year", type=int, default=None)
    ap.add_argument("--target-quarter", type=int, choices=[1, 2, 3, 4], default=None)
    ap.add_argument("--panel-start-year", type=int, default=2005)
    ap.add_argument("--stata-bin", default="stata-mp")
    ap.add_argument("--timeout-seconds", type=int, default=4 * 60 * 60)
    ap.add_argument("--run-qc", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--overwrite-download", action="store_true")
    ap.add_argument("--force-scaffold", action="store_true")
    ap.add_argument("--skip-detect", action="store_true")
    ap.add_argument("--skip-download", action="store_true")
    ap.add_argument("--skip-scaffold", action="store_true")
    ap.add_argument("--skip-schema", action="store_true")
    ap.add_argument("--skip-pipeline", action="store_true")
    ap.add_argument("--always-run-pipeline", action="store_true")
    ap.add_argument("--fail-on-schema-breaking", action="store_true")
    ap.add_argument("--out-dir", default=str(default_out_dir))
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_cmd(cmd: list[str], cwd: Path) -> dict[str, Any]:
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = round(time.time() - t0, 3)
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "elapsed_seconds": elapsed,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-6000:],
    }


def choose_latest_target_from_state(state: dict[str, Any]) -> tuple[int, int] | None:
    records = state.get("remote_records", {})
    if not isinstance(records, dict):
        return None
    candidates: list[tuple[int, int]] = []
    for payload in records.values():
        if not isinstance(payload, dict):
            continue
        try:
            year = int(payload.get("year"))
            quarter = int(payload.get("quarter"))
        except (TypeError, ValueError):
            continue
        if quarter in (1, 2, 3, 4):
            candidates.append((year, quarter))
    if not candidates:
        return None
    return sorted(candidates)[-1]


def prev_quarter(year: int, quarter: int) -> tuple[int, int]:
    if quarter > 1:
        return year, quarter - 1
    return year - 1, 4


def choose_original_zip(original_dir: Path, year: int, quarter: int) -> Path | None:
    preferred = [
        original_dir / f"original_MEX_{year}_ENOE-Q{quarter}.zip",
        original_dir / f"original_MEX_{year}-Q{quarter}.zip",
    ]
    for path in preferred:
        if path.exists():
            return path

    token = re.compile(rf"(?i){year}.*(?:ENOE-)?Q{quarter}")
    matching = [p for p in original_dir.glob("*.zip") if token.search(p.name)]
    if matching:
        return sorted(matching, key=lambda p: p.stat().st_mtime, reverse=True)[0]

    zips = list(original_dir.glob("*.zip"))
    if len(zips) == 1:
        return zips[0]
    return None


def zip_available_for_quarter(repo_root: Path, year: int, quarter: int) -> tuple[bool, str]:
    qroot = repo_root / f"MEX_{year}_ENOE-Q{quarter}"
    original_dir = qroot / f"MEX_{year}_ENOE_V01_M" / "Data" / "Original"
    if not original_dir.exists():
        return False, f"Original dir missing: {original_dir}"

    zip_path = choose_original_zip(original_dir, year, quarter)
    if zip_path is None:
        return False, f"No ZIP found for {year}-Q{quarter} under {original_dir}"

    return True, str(zip_path)


def aggregate_schema_status(*statuses: str) -> str:
    values = [s for s in statuses if s]
    if not values:
        return "n/a"
    if any(s == "failed" for s in values):
        return "failed"
    if any(s == "ok" for s in values):
        return "ok"
    if all(s.startswith("skipped") for s in values):
        return "skipped"
    return values[0]


def panel_tag(start_year: int, end_year: int, end_quarter: int) -> str:
    return f"{start_year}_{end_year}Q{end_quarter}"


def expected_panel_output(repo_root: Path, start_year: int, end_year: int, end_quarter: int) -> Path:
    tag = panel_tag(start_year, end_year, end_quarter)
    return repo_root / "PANEL" / "DATA" / f"MEX_{tag}_PANEL_QUARTER.dta"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    script_dir = Path(__file__).resolve().parent

    phase1 = script_dir / "phase1_detect_download.py"
    phase2_scaffold = script_dir / "phase2_scaffold_quarter.py"
    phase2_run = script_dir / "phase2_run_stata_pipeline.py"
    phase4_schema = script_dir / "phase4_schema_diff.py"
    state_file = repo_root / "Do-files" / "quarterly_agent" / "state" / "inegi_enoe_phase1_state.json"

    run_id = timestamp_slug()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / f"agent_run_{run_id}.json"

    summary: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "config": {
            "repo_root": str(repo_root),
            "years": args.years,
            "target_year": args.target_year,
            "target_quarter": args.target_quarter,
            "panel_start_year": args.panel_start_year,
            "stata_bin": args.stata_bin,
            "timeout_seconds": args.timeout_seconds,
            "dry_run": args.dry_run,
            "overwrite_download": args.overwrite_download,
            "force_scaffold": args.force_scaffold,
            "skip_detect": args.skip_detect,
            "skip_download": args.skip_download,
            "skip_scaffold": args.skip_scaffold,
            "skip_schema": args.skip_schema,
            "skip_pipeline": args.skip_pipeline,
            "always_run_pipeline": args.always_run_pipeline,
            "fail_on_schema_breaking": args.fail_on_schema_breaking,
            "run_qc": args.run_qc,
        },
        "steps": {},
        "status": "running",
    }

    fatal = False

    # Step 1: detect remote records in dry-run mode to resolve target.
    if args.skip_detect:
        summary["steps"]["detect"] = {"status": "skipped"}
    else:
        cmd = [
            sys.executable,
            str(phase1),
            "--repo-root",
            str(repo_root),
            "--years",
            args.years,
            "--format",
            "dta",
            "--dry-run",
        ]
        if args.verbose:
            cmd.append("--verbose")
        result = run_cmd(cmd, cwd=repo_root)
        result["status"] = "ok" if result["returncode"] == 0 else "failed"
        summary["steps"]["detect"] = result
        if result["returncode"] != 0:
            fatal = True

    state = read_json(state_file)

    # Resolve target quarter.
    if args.target_year is not None and args.target_quarter is not None:
        target_year, target_quarter = args.target_year, args.target_quarter
    elif args.target_year is None and args.target_quarter is None:
        latest = choose_latest_target_from_state(state)
        if latest is None:
            summary["status"] = "failed"
            summary["error"] = "Could not determine target quarter from phase1 state."
            write_json(summary_path, summary)
            print(summary["error"], file=sys.stderr)
            return 2
        target_year, target_quarter = latest
    else:
        summary["status"] = "failed"
        summary["error"] = "Provide both --target-year and --target-quarter, or neither."
        write_json(summary_path, summary)
        print(summary["error"], file=sys.stderr)
        return 2

    summary["target"] = {
        "year": target_year,
        "quarter": target_quarter,
        "label": f"{target_year}-Q{target_quarter}",
    }

    target_root = repo_root / f"MEX_{target_year}_ENOE-Q{target_quarter}"
    target_exists_before = target_root.exists()

    # Step 2: scaffold when needed.
    if args.skip_scaffold:
        summary["steps"]["scaffold"] = {"status": "skipped"}
    else:
        if target_exists_before and not args.force_scaffold:
            summary["steps"]["scaffold"] = {"status": "skipped_exists", "target_root": str(target_root)}
        else:
            cmd = [
                sys.executable,
                str(phase2_scaffold),
                "--repo-root",
                str(repo_root),
                "--target-year",
                str(target_year),
                "--target-quarter",
                str(target_quarter),
            ]
            if args.force_scaffold:
                cmd.append("--force")
            if args.dry_run:
                cmd.append("--dry-run")
            if args.verbose:
                cmd.append("--verbose")
            result = run_cmd(cmd, cwd=repo_root)
            result["status"] = "ok" if result["returncode"] == 0 else "failed"
            summary["steps"]["scaffold"] = result
            if result["returncode"] != 0:
                fatal = True

    # Step 3: download target-year artifacts (real or dry-run).
    if args.skip_download:
        summary["steps"]["download"] = {"status": "skipped"}
    else:
        cmd = [
            sys.executable,
            str(phase1),
            "--repo-root",
            str(repo_root),
            "--years",
            str(target_year),
            "--format",
            "dta",
        ]
        if args.dry_run:
            cmd.append("--dry-run")
        if args.overwrite_download:
            cmd.append("--overwrite")
        if args.verbose:
            cmd.append("--verbose")
        result = run_cmd(cmd, cwd=repo_root)
        result["status"] = "ok" if result["returncode"] == 0 else "failed"
        summary["steps"]["download"] = result
        if result["returncode"] != 0:
            fatal = True

    state = read_json(state_file)
    download_key = f"{target_year}-Q{target_quarter}-dta"
    download_status = ""
    if isinstance(state.get("downloads"), dict):
        item = state["downloads"].get(download_key, {})
        if isinstance(item, dict):
            download_status = str(item.get("status", ""))
    summary["download_key"] = download_key
    summary["download_status"] = download_status

    # Step 4: schema diff (dual checks: sequential + year-over-year).
    if args.skip_schema or fatal:
        blocked_status = "skipped" if args.skip_schema else "blocked"
        summary["steps"]["schema_prev"] = {"status": blocked_status}
        summary["steps"]["schema_yoy"] = {"status": blocked_status}
        summary["steps"]["schema"] = {"status": blocked_status}
    else:
        # 4A. Sequential check: target versus previous quarter.
        prev_year, prev_q = prev_quarter(target_year, target_quarter)
        prev_ok, prev_detail = zip_available_for_quarter(repo_root, prev_year, prev_q)
        if not prev_ok:
            summary["steps"]["schema_prev"] = {
                "status": "skipped_missing_base",
                "comparison": "previous_quarter",
                "base": {"year": prev_year, "quarter": prev_q, "label": f"{prev_year}-Q{prev_q}"},
                "target": {"year": target_year, "quarter": target_quarter, "label": f"{target_year}-Q{target_quarter}"},
                "reason": prev_detail,
            }
        else:
            cmd_prev = [
                sys.executable,
                str(phase4_schema),
                "--repo-root",
                str(repo_root),
                "--target-year",
                str(target_year),
                "--target-quarter",
                str(target_quarter),
                "--base-year",
                str(prev_year),
                "--base-quarter",
                str(prev_q),
                "--comparison-tag",
                "prev",
                "--stata-bin",
                args.stata_bin,
                "--timeout-seconds",
                str(min(args.timeout_seconds, 120)),
            ]
            if args.fail_on_schema_breaking:
                cmd_prev.append("--fail-on-breaking")
            if args.verbose:
                cmd_prev.append("--verbose")
            result_prev = run_cmd(cmd_prev, cwd=repo_root)
            result_prev["status"] = "ok" if result_prev["returncode"] == 0 else "failed"
            result_prev["comparison"] = "previous_quarter"
            result_prev["base"] = {"year": prev_year, "quarter": prev_q, "label": f"{prev_year}-Q{prev_q}"}
            result_prev["target"] = {"year": target_year, "quarter": target_quarter, "label": f"{target_year}-Q{target_quarter}"}
            summary["steps"]["schema_prev"] = result_prev
            if result_prev["returncode"] != 0:
                fatal = True

        # 4B. Year-over-year check: target versus same quarter in prior year.
        yoy_year, yoy_q = target_year - 1, target_quarter
        yoy_ok, yoy_detail = zip_available_for_quarter(repo_root, yoy_year, yoy_q)
        if not yoy_ok:
            summary["steps"]["schema_yoy"] = {
                "status": "skipped_missing_base",
                "comparison": "year_over_year_same_quarter",
                "base": {"year": yoy_year, "quarter": yoy_q, "label": f"{yoy_year}-Q{yoy_q}"},
                "target": {"year": target_year, "quarter": target_quarter, "label": f"{target_year}-Q{target_quarter}"},
                "reason": yoy_detail,
            }
        else:
            cmd_yoy = [
                sys.executable,
                str(phase4_schema),
                "--repo-root",
                str(repo_root),
                "--target-year",
                str(target_year),
                "--target-quarter",
                str(target_quarter),
                "--base-year",
                str(yoy_year),
                "--base-quarter",
                str(yoy_q),
                "--comparison-tag",
                "yoy",
                "--stata-bin",
                args.stata_bin,
                "--timeout-seconds",
                str(min(args.timeout_seconds, 120)),
            ]
            if args.fail_on_schema_breaking:
                cmd_yoy.append("--fail-on-breaking")
            if args.verbose:
                cmd_yoy.append("--verbose")
            result_yoy = run_cmd(cmd_yoy, cwd=repo_root)
            result_yoy["status"] = "ok" if result_yoy["returncode"] == 0 else "failed"
            result_yoy["comparison"] = "year_over_year_same_quarter"
            result_yoy["base"] = {"year": yoy_year, "quarter": yoy_q, "label": f"{yoy_year}-Q{yoy_q}"}
            result_yoy["target"] = {"year": target_year, "quarter": target_quarter, "label": f"{target_year}-Q{target_quarter}"}
            summary["steps"]["schema_yoy"] = result_yoy
            if result_yoy["returncode"] != 0:
                fatal = True

        summary["steps"]["schema"] = {
            "status": aggregate_schema_status(
                summary["steps"].get("schema_prev", {}).get("status", ""),
                summary["steps"].get("schema_yoy", {}).get("status", ""),
            ),
            "checks": ["schema_prev", "schema_yoy"],
        }

    # Step 5: phase2 pipeline execution decision.
    expected_panel = expected_panel_output(repo_root, args.panel_start_year, target_year, target_quarter)
    should_run_pipeline = (
        args.always_run_pipeline
        or args.dry_run
        or download_status in {"downloaded"}
        or not expected_panel.exists()
    )
    summary["expected_panel_output"] = str(expected_panel)
    summary["pipeline_decision"] = "run" if should_run_pipeline else "skip_no_change"

    if args.skip_pipeline or fatal:
        summary["steps"]["pipeline"] = {"status": "skipped" if args.skip_pipeline else "blocked"}
    elif not should_run_pipeline:
        summary["steps"]["pipeline"] = {"status": "skipped_no_change"}
    else:
        cmd = [
            sys.executable,
            str(phase2_run),
            "--repo-root",
            str(repo_root),
            "--year",
            str(target_year),
            "--quarter",
            str(target_quarter),
            "--panel-start-year",
            str(args.panel_start_year),
            "--stata-bin",
            args.stata_bin,
            "--timeout-seconds",
            str(args.timeout_seconds),
        ]
        if args.run_qc:
            cmd.append("--run-qc")
        if args.dry_run:
            cmd.append("--dry-run")
        if args.verbose:
            cmd.append("--verbose")
        result = run_cmd(cmd, cwd=repo_root)
        result["status"] = "ok" if result["returncode"] == 0 else "failed"
        summary["steps"]["pipeline"] = result
        if result["returncode"] != 0:
            fatal = True

    summary["status"] = "failed" if fatal else "ok"
    write_json(summary_path, summary)

    print(f"Quarterly agent status: {summary['status']}")
    print(f"Summary: {summary_path}")
    for step in ("detect", "scaffold", "download", "schema_prev", "schema_yoy", "schema", "pipeline"):
        status = summary["steps"].get(step, {}).get("status", "n/a")
        print(f"{step}: {status}")

    return 1 if fatal else 0


if __name__ == "__main__":
    raise SystemExit(main())
