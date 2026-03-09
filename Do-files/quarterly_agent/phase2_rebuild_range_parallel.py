#!/usr/bin/env python3
"""Phase 2C: parallel quarter rebuild with OneDrive safety gate."""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from versioning import ENOEVersionConfig, fullsample_output_path, harm_output_path, load_version_config, panel_output_path, quarter_root


@dataclass(frozen=True)
class QuarterRef:
    year: int
    quarter: int

    @property
    def label(self) -> str:
        return f"{self.year}-Q{self.quarter}"


KNOWN_MISSING_QUARTERS: dict[tuple[int, int], str] = {
    (2020, 2): "ENOE 2020-Q2 is not available in-source (COVID-19 interruption).",
}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_state = default_repo / "Do-files" / "quarterly_agent" / "state" / "rebuild_parallel"
    default_ack = default_repo / "Do-files" / "quarterly_agent" / "state" / "locks" / "onedrive_paused.ok"

    ap = argparse.ArgumentParser(description="Parallel ENOE range rebuild with OneDrive pause gate")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--start-year", type=int, required=True)
    ap.add_argument("--start-quarter", type=int, choices=[1, 2, 3, 4], default=1)
    ap.add_argument("--end-year", type=int, required=True)
    ap.add_argument("--end-quarter", type=int, choices=[1, 2, 3, 4], default=4)
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--panel-start-year", type=int, default=2005)
    ap.add_argument("--stata-bin", default="stata-mp")
    ap.add_argument("--timeout-seconds", type=int, default=4 * 60 * 60)
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-finalize", action="store_true")
    ap.add_argument("--finalize-skip-extract", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--run-qc", action="store_true")
    ap.add_argument("--continue-on-error", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--state-dir", default=str(default_state))

    ap.add_argument("--require-onedrive-paused", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--onedrive-ack-file", default=str(default_ack))
    ap.add_argument("--onedrive-ack-max-age-minutes", type=int, default=240)
    ap.add_argument("--wait-for-onedrive", action="store_true")
    ap.add_argument("--wait-timeout-seconds", type=int, default=3600)
    ap.add_argument("--poll-seconds", type=int, default=15)
    return ap.parse_args()


def quarter_seq(start: QuarterRef, end: QuarterRef) -> list[QuarterRef]:
    if (end.year, end.quarter) < (start.year, start.quarter):
        raise ValueError("end quarter must be greater than or equal to start quarter")
    out: list[QuarterRef] = []
    yy, qq = start.year, start.quarter
    while (yy, qq) <= (end.year, end.quarter):
        out.append(QuarterRef(yy, qq))
        qq += 1
        if qq > 4:
            yy += 1
            qq = 1
    return out


def ack_status(path: Path, max_age_minutes: int) -> dict[str, Any]:
    now = dt.datetime.now(dt.timezone.utc)
    payload: dict[str, Any] = {
        "path": str(path),
        "exists": path.exists(),
        "max_age_minutes": max_age_minutes,
        "is_valid": False,
    }
    if not path.exists():
        payload["reason"] = "missing_ack_file"
        return payload

    stat = path.stat()
    mtime = dt.datetime.fromtimestamp(stat.st_mtime, tz=dt.timezone.utc)
    age_seconds = (now - mtime).total_seconds()
    payload["mtime_utc"] = mtime.replace(microsecond=0).isoformat()
    payload["age_seconds"] = round(age_seconds, 3)

    if max_age_minutes > 0 and age_seconds > max_age_minutes * 60:
        payload["reason"] = "stale_ack_file"
        return payload

    payload["is_valid"] = True
    payload["reason"] = "ok"
    return payload


def enforce_onedrive_gate(
    ack_file: Path,
    require_paused: bool,
    max_age_minutes: int,
    wait_for_onedrive: bool,
    wait_timeout_seconds: int,
    poll_seconds: int,
) -> dict[str, Any]:
    if not require_paused:
        return {
            "status": "skipped",
            "reason": "require_onedrive_paused_false",
            "path": str(ack_file),
        }

    initial = ack_status(ack_file, max_age_minutes)
    if initial["is_valid"]:
        return {"status": "ok", "check": initial}

    if not wait_for_onedrive:
        return {
            "status": "blocked",
            "check": initial,
            "instructions": [
                "Pause OneDrive sync manually from the system tray/menu bar.",
                f"Confirm pause with: touch {ack_file}",
                "Re-run the command.",
            ],
        }

    t0 = time.time()
    checks: list[dict[str, Any]] = [initial]
    while True:
        if time.time() - t0 > wait_timeout_seconds:
            return {
                "status": "blocked_timeout",
                "wait_seconds": wait_timeout_seconds,
                "checks": checks[-10:],
                "path": str(ack_file),
            }
        time.sleep(max(1, poll_seconds))
        current = ack_status(ack_file, max_age_minutes)
        checks.append(current)
        if current["is_valid"]:
            return {
                "status": "ok",
                "waited_seconds": round(time.time() - t0, 3),
                "check": current,
            }


def harmonized_output_path(repo_root: Path, cfg: ENOEVersionConfig, q: QuarterRef) -> Path:
    return harm_output_path(quarter_root(repo_root, cfg, q.year, q.quarter), cfg, q.year)


def run_cmd(cmd: list[str], cwd: Path) -> dict[str, Any]:
    t0 = time.time()
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    elapsed = round(time.time() - t0, 3)
    return {
        "cmd": cmd,
        "cwd": str(cwd),
        "returncode": proc.returncode,
        "elapsed_seconds": elapsed,
        "stdout_tail": proc.stdout[-10000:],
        "stderr_tail": proc.stderr[-10000:],
    }


def parse_summary_path(stdout_tail: str) -> str:
    hits = re.findall(r"Summary:\s*(.+)", stdout_tail)
    return hits[-1].strip() if hits else ""


def run_harmonization_job(
    repo_root: Path,
    cfg: ENOEVersionConfig,
    phase2_script: Path,
    q: QuarterRef,
    args: argparse.Namespace,
) -> dict[str, Any]:
    missing_reason = KNOWN_MISSING_QUARTERS.get((q.year, q.quarter))
    if missing_reason:
        expected = harmonized_output_path(repo_root, cfg, q)
        return {
            "quarter": {"year": q.year, "quarter": q.quarter, "label": q.label},
            "status": "skipped",
            "skip_reason": missing_reason,
            "cmd": [],
            "cwd": str(repo_root),
            "returncode": 0,
            "elapsed_seconds": 0.0,
            "stdout_tail": "",
            "stderr_tail": "",
            "summary_path": "",
            "harmonized_output": str(expected),
            "harmonized_output_exists": expected.exists(),
        }

    cmd = [
        sys.executable,
        str(phase2_script),
        "--repo-root",
        str(repo_root),
        "--year",
        str(q.year),
        "--quarter",
        str(q.quarter),
        "--panel-start-year",
        str(args.panel_start_year),
        "--stata-bin",
        args.stata_bin,
        "--timeout-seconds",
        str(args.timeout_seconds),
        "--skip-append",
        "--skip-panel",
    ]
    if args.skip_extract:
        cmd.append("--skip-extract")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    result = run_cmd(cmd, cwd=repo_root)
    result["quarter"] = {"year": q.year, "quarter": q.quarter, "label": q.label}
    result["summary_path"] = parse_summary_path(result["stdout_tail"])

    expected = harmonized_output_path(repo_root, cfg, q)
    result["harmonized_output"] = str(expected)
    result["harmonized_output_exists"] = expected.exists()

    ok = result["returncode"] == 0 and (args.dry_run or expected.exists())
    result["status"] = "ok" if ok else "failed"
    return result


def run_finalize(
    repo_root: Path,
    cfg: ENOEVersionConfig,
    phase2_script: Path,
    end_q: QuarterRef,
    args: argparse.Namespace,
) -> dict[str, Any]:
    cmd = [
        sys.executable,
        str(phase2_script),
        "--repo-root",
        str(repo_root),
        "--year",
        str(end_q.year),
        "--quarter",
        str(end_q.quarter),
        "--panel-start-year",
        str(args.panel_start_year),
        "--stata-bin",
        args.stata_bin,
        "--timeout-seconds",
        str(args.timeout_seconds),
    ]
    if args.finalize_skip_extract:
        cmd.append("--skip-extract")
    if args.run_qc:
        cmd.append("--run-qc")
    if args.dry_run:
        cmd.append("--dry-run")
    if args.verbose:
        cmd.append("--verbose")

    result = run_cmd(cmd, cwd=repo_root)
    result["summary_path"] = parse_summary_path(result["stdout_tail"])

    expected_full = fullsample_output_path(repo_root, cfg, args.panel_start_year, end_q.year, end_q.quarter)
    expected_panel = panel_output_path(repo_root, cfg, args.panel_start_year, end_q.year, end_q.quarter)
    result["expected_fullsample"] = str(expected_full)
    result["expected_panel"] = str(expected_panel)
    result["fullsample_exists"] = expected_full.exists()
    result["panel_exists"] = expected_panel.exists()
    ok = result["returncode"] == 0 and (args.dry_run or (expected_full.exists() and expected_panel.exists()))
    result["status"] = "ok" if ok else "failed"
    return result


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cfg = load_version_config(repo_root)
    state_dir = Path(args.state_dir).resolve()
    ack_file = Path(args.onedrive_ack_file).resolve()
    phase2_script = Path(__file__).resolve().parent / "phase2_run_stata_pipeline.py"

    start = QuarterRef(args.start_year, args.start_quarter)
    end = QuarterRef(args.end_year, args.end_quarter)
    quarters = quarter_seq(start, end)

    if args.panel_start_year > args.start_year:
        print("ERROR: --panel-start-year must be <= --start-year", file=sys.stderr)
        return 2
    if args.workers < 1:
        print("ERROR: --workers must be >= 1", file=sys.stderr)
        return 2

    run_id = timestamp_slug()
    summary_path = state_dir / f"phase2_rebuild_parallel_{run_id}.json"

    summary: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "config": {
            "repo_root": str(repo_root),
            "start_year": args.start_year,
            "start_quarter": args.start_quarter,
            "end_year": args.end_year,
            "end_quarter": args.end_quarter,
            "workers": args.workers,
            "panel_start_year": args.panel_start_year,
            "stata_bin": args.stata_bin,
            "timeout_seconds": args.timeout_seconds,
            "skip_extract": args.skip_extract,
            "skip_finalize": args.skip_finalize,
            "finalize_skip_extract": args.finalize_skip_extract,
            "run_qc": args.run_qc,
            "continue_on_error": args.continue_on_error,
            "dry_run": args.dry_run,
            "require_onedrive_paused": args.require_onedrive_paused,
            "onedrive_ack_file": str(ack_file),
            "onedrive_ack_max_age_minutes": args.onedrive_ack_max_age_minutes,
            "wait_for_onedrive": args.wait_for_onedrive,
            "wait_timeout_seconds": args.wait_timeout_seconds,
            "poll_seconds": args.poll_seconds,
        },
        "quarters": [{"year": q.year, "quarter": q.quarter, "label": q.label} for q in quarters],
        "steps": {},
        "status": "running",
    }

    gate = enforce_onedrive_gate(
        ack_file=ack_file,
        require_paused=args.require_onedrive_paused,
        max_age_minutes=args.onedrive_ack_max_age_minutes,
        wait_for_onedrive=args.wait_for_onedrive,
        wait_timeout_seconds=args.wait_timeout_seconds,
        poll_seconds=args.poll_seconds,
    )
    summary["steps"]["onedrive_gate"] = gate
    if gate.get("status") != "ok" and gate.get("status") != "skipped":
        summary["status"] = "blocked"
        summary["error"] = "OneDrive gate not satisfied."
        write_json(summary_path, summary)
        print("Parallel rebuild blocked: OneDrive gate not satisfied.", file=sys.stderr)
        print(f"Summary: {summary_path}")
        return 2

    jobs: list[dict[str, Any]] = []
    failed = False
    if args.workers == 1:
        for q in quarters:
            result = run_harmonization_job(repo_root, cfg, phase2_script, q, args)
            jobs.append(result)
            if result["status"] not in {"ok", "skipped"}:
                failed = True
                if not args.continue_on_error:
                    break
    else:
        with cf.ThreadPoolExecutor(max_workers=args.workers) as ex:
            future_map = {
                ex.submit(run_harmonization_job, repo_root, cfg, phase2_script, q, args): q
                for q in quarters
            }
            for fut in cf.as_completed(future_map):
                res = fut.result()
                jobs.append(res)
                if args.verbose:
                    q = res["quarter"]["label"]
                    print(f"{q}: {res['status']}")
                if res["status"] not in {"ok", "skipped"}:
                    failed = True
                    if not args.continue_on_error:
                        # Already-submitted jobs will finish; we only block finalize.
                        pass

    jobs.sort(key=lambda x: (int(x["quarter"]["year"]), int(x["quarter"]["quarter"])))
    summary["steps"]["parallel_harmonization"] = {
        "status": "ok" if not failed else "failed",
        "workers": args.workers,
        "jobs": jobs,
    }

    if args.skip_finalize:
        summary["steps"]["finalize"] = {"status": "skipped"}
    elif failed:
        summary["steps"]["finalize"] = {
            "status": "blocked",
            "reason": "harmonization_failures_present",
        }
    else:
        final_res = run_finalize(repo_root, cfg, phase2_script, end, args)
        summary["steps"]["finalize"] = final_res
        if final_res["status"] != "ok":
            failed = True

    summary["status"] = "failed" if failed else "ok"
    write_json(summary_path, summary)

    print(f"Parallel rebuild status: {summary['status']}")
    print(f"Summary: {summary_path}")
    print(f"onedrive_gate: {summary['steps']['onedrive_gate'].get('status', 'n/a')}")
    print(f"parallel_harmonization: {summary['steps']['parallel_harmonization'].get('status', 'n/a')}")
    print(f"finalize: {summary['steps']['finalize'].get('status', 'n/a')}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
