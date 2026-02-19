#!/usr/bin/env python3
"""Phase 2B: extract ENOE quarter files and run Stata harmonization/panel pipeline."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any


LICENSE_ERROR_PATTERNS = (
    r"\blicense\s+has\s+expired\b",
    r"\blicense\b.{0,80}\bexpired\b",
    r"\bexpired\s+license\b",
    r"\bno\s+valid\s+license\b",
    r"\bnot\s+licensed\b",
    r"\blicense\s+file\b.{0,80}\b(not\s+found|cannot|could\s+not|invalid|error)\b",
    r"\bauthorization\s+code\b.{0,80}\b(invalid|expired|incorrect)\b",
)


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    ap = argparse.ArgumentParser(description="Run quarter extract + Stata harmonization + append/panel")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--quarter", type=int, choices=[1, 2, 3, 4], required=True)
    ap.add_argument("--panel-start-year", type=int, default=2005)
    ap.add_argument("--stata-bin", default="stata-mp")
    ap.add_argument("--skip-extract", action="store_true")
    ap.add_argument("--skip-append", action="store_true")
    ap.add_argument("--skip-panel", action="store_true")
    ap.add_argument("--run-qc", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout-seconds", type=int, default=4 * 60 * 60)
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args()


def quarter_suffix(year: int, quarter: int) -> str:
    return f"{quarter}{str(year)[2:]}"


def quarter_root(repo_root: Path, year: int, quarter: int) -> Path:
    return repo_root / f"MEX_{year}_ENOE-Q{quarter}"


def master_dir(root: Path, year: int) -> Path:
    return root / f"MEX_{year}_ENOE_V01_M"


def harm_dir(root: Path, year: int) -> Path:
    return root / f"MEX_{year}_ENOE_V01_M_V06_A_GLD"


def harm_program_path(root: Path, year: int) -> Path:
    return harm_dir(root, year) / "Programs" / f"MEX_{year}_ENOE_V01_M_V06_A_GLD_ALL.do"


def harm_output_path(root: Path, year: int) -> Path:
    return harm_dir(root, year) / "Data" / "Harmonized" / f"MEX_{year}_ENOE_V01_M_V06_A_GLD_ALL.dta"


def state_run_dir(repo_root: Path) -> Path:
    return repo_root / "Do-files" / "quarterly_agent" / "state" / "runs"


def panel_tag(start_year: int, end_year: int, end_quarter: int) -> str:
    return f"{start_year}_{end_year}Q{end_quarter}"


def fullsample_output_path(repo_root: Path, start_year: int, end_year: int, end_quarter: int) -> Path:
    tag = panel_tag(start_year, end_year, end_quarter)
    return repo_root / "PANEL" / "DATA" / f"MEX_{tag}_ENOE_V01_M_V06_A_GLD_FULLSAMPLE.dta"


def fullsample_latest_alias_path(repo_root: Path) -> Path:
    return repo_root / "PANEL" / "DATA" / "MEX_ENOE_V01_M_V06_A_GLD_FULLSAMPLE_latest.dta"


def panel_output_path(repo_root: Path, start_year: int, end_year: int, end_quarter: int) -> Path:
    tag = panel_tag(start_year, end_year, end_quarter)
    return repo_root / "PANEL" / "DATA" / f"MEX_{tag}_PANEL_QUARTER.dta"


def panel_latest_alias_path(repo_root: Path) -> Path:
    return repo_root / "PANEL" / "DATA" / "MEX_PANEL_QUARTER_latest.dta"


def pipeline_globals(start_year: int, end_year: int, end_quarter: int) -> dict[str, str]:
    return {
        "panel_start_year": str(start_year),
        "panel_end_year": str(end_year),
        "panel_end_quarter": str(end_quarter),
    }


def choose_original_zip(original_dir: Path, year: int, quarter: int) -> Path | None:
    candidates = [
        original_dir / f"original_MEX_{year}_ENOE-Q{quarter}.zip",
        original_dir / f"original_MEX_{year}-Q{quarter}.zip",
    ]
    for c in candidates:
        if c.exists():
            return c
    token = re.compile(rf"(?i){year}.*(?:ENOE-)?Q{quarter}")
    matching = [p for p in original_dir.glob("*.zip") if token.search(p.name)]
    if matching:
        return sorted(matching, key=lambda p: p.stat().st_mtime, reverse=True)[0]
    zips = list(original_dir.glob("*.zip"))
    if len(zips) == 1:
        return zips[0]
    return None


def extract_zip_to_stata(zip_path: Path, stata_dir: Path) -> dict[str, Any]:
    stata_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(tdir)
        for src in sorted(tdir.rglob("*.dta")):
            dst = stata_dir / src.name
            shutil.copy2(src, dst)
            copied.append(dst.name)
    return {"copied_count": len(copied), "files": copied}


def find_required_stata_files(stata_dir: Path, suffix: str) -> dict[str, str]:
    found: dict[str, str] = {}
    patterns = {
        "COE1T": re.compile(rf"(?i)^(?:enoe_|enoen_)?coe1t{suffix}\.dta$"),
        "COE2T": re.compile(rf"(?i)^(?:enoe_|enoen_)?coe2t{suffix}\.dta$"),
        "SDEMT": re.compile(rf"(?i)^(?:enoe_|enoen_)?sdemt{suffix}\.dta$"),
        "HOGT": re.compile(rf"(?i)^(?:enoe_|enoen_)?hogt{suffix}\.dta$"),
        "VIVT": re.compile(rf"(?i)^(?:enoe_|enoen_)?vivt{suffix}\.dta$"),
    }
    files = [p.name for p in stata_dir.glob("*.dta")]
    for token, patt in patterns.items():
        for name in files:
            if patt.match(name):
                found[token] = name
                break
    return found


def find_required_files_in_zip(zip_path: Path, suffix: str) -> dict[str, str]:
    found: dict[str, str] = {}
    patterns = {
        "COE1T": re.compile(rf"(?i)^(?:enoe_|enoen_)?coe1t{suffix}\.dta$"),
        "COE2T": re.compile(rf"(?i)^(?:enoe_|enoen_)?coe2t{suffix}\.dta$"),
        "SDEMT": re.compile(rf"(?i)^(?:enoe_|enoen_)?sdemt{suffix}\.dta$"),
        "HOGT": re.compile(rf"(?i)^(?:enoe_|enoen_)?hogt{suffix}\.dta$"),
        "VIVT": re.compile(rf"(?i)^(?:enoe_|enoen_)?vivt{suffix}\.dta$"),
    }
    try:
        with zipfile.ZipFile(zip_path, "r") as zf:
            files = [Path(n).name for n in zf.namelist() if n.lower().endswith(".dta")]
    except zipfile.BadZipFile:
        return found
    for token, patt in patterns.items():
        for name in files:
            if patt.match(name):
                found[token] = name
                break
    return found


def run_stata_do(stata_bin: str, do_path: Path, timeout_seconds: int, cwd: Path | None = None) -> dict[str, Any]:
    cmd = [stata_bin, "-b", "do", str(do_path)]
    run_cwd = cwd if cwd is not None else do_path.parent
    try:
        proc = subprocess.run(
            cmd,
            cwd=run_cwd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env=os.environ.copy(),
        )
    except FileNotFoundError:
        return {
            "cmd": cmd,
            "cwd": str(run_cwd),
            "returncode": 127,
            "stdout_tail": "",
            "stderr_tail": "",
            "diagnostic": {
                "category": "binary_not_found",
                "message": f"Stata executable not found: {stata_bin}",
            },
        }
    except subprocess.TimeoutExpired:
        return {
            "cmd": cmd,
            "cwd": str(run_cwd),
            "returncode": 124,
            "stdout_tail": "",
            "stderr_tail": "",
            "diagnostic": {
                "category": "timeout",
                "message": f"Stata command exceeded timeout ({timeout_seconds}s).",
            },
        }

    result = {
        "cmd": cmd,
        "cwd": str(run_cwd),
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }
    log_path = run_cwd / f"{do_path.stem}.log"
    result["log_path"] = str(log_path)
    if log_path.exists():
        result["log_tail"] = read_text_tail(log_path, 12000)
    diagnostic = classify_stata_issue(result)
    if diagnostic:
        result["diagnostic"] = diagnostic
    return result


def classify_stata_issue(run_result: dict[str, Any]) -> dict[str, str] | None:
    text = (
        f"{run_result.get('stdout_tail', '')}\n"
        f"{run_result.get('stderr_tail', '')}\n"
        f"{run_result.get('log_tail', '')}"
    ).lower()
    for pat in LICENSE_ERROR_PATTERNS:
        if re.search(pat, text):
            return {
                "category": "license",
                "message": "Stata license issue detected (expired/invalid license).",
            }

    if "too many users" in text or "all in use" in text:
        return {
            "category": "license_seat",
            "message": "Stata license seat unavailable (all seats in use).",
        }

    return None


def write_wrapper_do(path: Path, repo_root: Path, inner_do_rel: str, extra_globals: dict[str, str] | None = None) -> None:
    globals_block = ""
    if extra_globals:
        for key, value in extra_globals.items():
            globals_block += f'global {key} "{value}"\n'
    content = (
        "clear\n"
        "set more off\n"
        f'global path "{repo_root.as_posix()}"\n'
        f"{globals_block}"
        'cd "$path"\n'
        f'do "{inner_do_rel}"\n'
    )
    path.write_text(content, encoding="utf-8")


def write_preflight_do(path: Path) -> None:
    content = (
        "clear\n"
        "set more off\n"
        'display "ENOE_PIPELINE_STATA_PREFLIGHT_OK"\n'
        "exit 0\n"
    )
    path.write_text(content, encoding="utf-8")


def read_text_tail(path: Path, max_chars: int) -> str:
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return text[-max_chars:]


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def extract_error_from_steps(steps: dict[str, Any]) -> str | None:
    order = ("stata_preflight", "harmonization", "append", "panel", "qc")
    for step_name in order:
        step = steps.get(step_name)
        if not isinstance(step, dict):
            continue
        diagnostic = step.get("diagnostic")
        if isinstance(diagnostic, dict) and diagnostic.get("message"):
            return f"{step_name}: {diagnostic['message']}"
        if step.get("error"):
            return f"{step_name}: {step['error']}"
    return None


def main() -> int:
    args = parse_args()
    if args.panel_start_year > args.year:
        print("ERROR: --panel-start-year must be <= --year", file=sys.stderr)
        return 2

    repo_root = Path(args.repo_root).resolve()
    panel_tag_value = panel_tag(args.panel_start_year, args.year, args.quarter)
    expected_fullsample = fullsample_output_path(repo_root, args.panel_start_year, args.year, args.quarter)
    expected_fullsample_latest = fullsample_latest_alias_path(repo_root)
    expected_panel = panel_output_path(repo_root, args.panel_start_year, args.year, args.quarter)
    expected_panel_latest = panel_latest_alias_path(repo_root)
    do_globals = pipeline_globals(args.panel_start_year, args.year, args.quarter)

    qroot = quarter_root(repo_root, args.year, args.quarter)
    mdir = master_dir(qroot, args.year)
    hprog = harm_program_path(qroot, args.year)
    hout = harm_output_path(qroot, args.year)
    orig_dir = mdir / "Data" / "Original"
    stata_dir = mdir / "Data" / "Stata"

    run_dir = state_run_dir(repo_root)
    run_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{args.year}Q{args.quarter}_{timestamp_slug()}"
    summary_path = run_dir / f"phase2_run_{run_id}.json"
    wrapper_append = run_dir / f"tmp_append_{run_id}.do"
    wrapper_panel = run_dir / f"tmp_panel_{run_id}.do"
    wrapper_qc = run_dir / f"tmp_qc_{run_id}.do"
    wrapper_preflight = run_dir / f"tmp_preflight_{run_id}.do"

    summary: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "config": {
            "year": args.year,
            "quarter": args.quarter,
            "panel_start_year": args.panel_start_year,
            "panel_tag": panel_tag_value,
            "dry_run": args.dry_run,
            "skip_extract": args.skip_extract,
            "skip_append": args.skip_append,
            "skip_panel": args.skip_panel,
            "run_qc": args.run_qc,
            "stata_bin": args.stata_bin,
            "timeout_seconds": args.timeout_seconds,
        },
        "paths": {
            "repo_root": str(repo_root),
            "quarter_root": str(qroot),
            "original_dir": str(orig_dir),
            "stata_dir": str(stata_dir),
            "harm_do": str(hprog),
            "harm_output": str(hout),
            "fullsample_output": str(expected_fullsample),
            "fullsample_latest_alias": str(expected_fullsample_latest),
            "panel_output": str(expected_panel),
            "panel_latest_alias": str(expected_panel_latest),
        },
        "steps": {},
        "status": "running",
    }

    fatal_error = False

    if not qroot.exists():
        summary["status"] = "failed"
        summary["error"] = f"Quarter root not found: {qroot}"
        write_json(summary_path, summary)
        print(summary["error"], file=sys.stderr)
        return 2

    if not hprog.exists():
        summary["status"] = "failed"
        summary["error"] = f"Harmonization do-file not found: {hprog}"
        write_json(summary_path, summary)
        print(summary["error"], file=sys.stderr)
        return 2

    zip_path = choose_original_zip(orig_dir, args.year, args.quarter)
    summary["paths"]["zip_path"] = str(zip_path) if zip_path else ""
    if zip_path is None:
        summary["status"] = "failed"
        summary["error"] = f"No unique ZIP candidate found in {orig_dir} for {args.year}-Q{args.quarter}"
        write_json(summary_path, summary)
        print(summary["error"], file=sys.stderr)
        return 2

    if args.dry_run:
        summary["steps"]["stata_preflight"] = {"status": "would_run"}
    else:
        write_preflight_do(wrapper_preflight)
        preflight = run_stata_do(args.stata_bin, wrapper_preflight, min(args.timeout_seconds, 120), cwd=repo_root)
        preflight_ok = preflight["returncode"] == 0 and "diagnostic" not in preflight
        preflight["status"] = "ok" if preflight_ok else "failed"
        summary["steps"]["stata_preflight"] = preflight
        if not preflight_ok:
            fatal_error = True

    suffix = quarter_suffix(args.year, args.quarter)
    if not fatal_error:
        if not args.skip_extract:
            if args.dry_run:
                summary["steps"]["extract"] = {"status": "would_extract", "zip_path": str(zip_path)}
            else:
                try:
                    extract_info = extract_zip_to_stata(zip_path, stata_dir)
                    summary["steps"]["extract"] = {"status": "ok", **extract_info}
                except Exception as exc:  # noqa: BLE001
                    summary["steps"]["extract"] = {"status": "failed", "error": str(exc)}
                    fatal_error = True
        else:
            summary["steps"]["extract"] = {"status": "skipped"}

        if args.dry_run and not args.skip_extract:
            required = find_required_files_in_zip(zip_path, suffix)
            checked_from = "zip"
        else:
            required = find_required_stata_files(stata_dir, suffix)
            checked_from = "stata"
        missing = [tok for tok in ("COE1T", "COE2T", "SDEMT", "HOGT", "VIVT") if tok not in required]
        summary["steps"]["validate_inputs"] = {
            "status": "ok" if not missing else "failed",
            "suffix": suffix,
            "checked_from": checked_from,
            "found": required,
            "missing": missing,
        }
        if missing:
            fatal_error = True

        if not fatal_error:
            if args.dry_run:
                summary["steps"]["harmonization"] = {"status": "would_run", "do_file": str(hprog)}
            else:
                try:
                    result = run_stata_do(args.stata_bin, hprog, args.timeout_seconds, cwd=hprog.parent)
                    ok = result["returncode"] == 0 and hout.exists()
                    result["harm_output_exists"] = hout.exists()
                    result["status"] = "ok" if ok else "failed"
                    summary["steps"]["harmonization"] = result
                    if not ok:
                        fatal_error = True
                except Exception as exc:  # noqa: BLE001
                    summary["steps"]["harmonization"] = {"status": "failed", "error": str(exc)}
                    fatal_error = True
        else:
            summary["steps"]["harmonization"] = {"status": "blocked"}
    else:
        summary["steps"]["extract"] = {"status": "blocked"}
        summary["steps"]["validate_inputs"] = {"status": "blocked", "suffix": suffix}
        summary["steps"]["harmonization"] = {"status": "blocked"}

    if not fatal_error and not args.skip_append:
        write_wrapper_do(wrapper_append, repo_root, "Do-files/02_Append_ENOE_Surveys.do", extra_globals=do_globals)
        if args.dry_run:
            summary["steps"]["append"] = {"status": "would_run", "wrapper_do": str(wrapper_append)}
        else:
            try:
                result = run_stata_do(args.stata_bin, wrapper_append, args.timeout_seconds, cwd=repo_root)
                ok = result["returncode"] == 0 and expected_fullsample.exists()
                result["fullsample_exists"] = expected_fullsample.exists()
                result["fullsample_latest_exists"] = expected_fullsample_latest.exists()
                result["status"] = "ok" if ok else "failed"
                summary["steps"]["append"] = result
                if not ok:
                    fatal_error = True
            except Exception as exc:  # noqa: BLE001
                summary["steps"]["append"] = {"status": "failed", "error": str(exc)}
                fatal_error = True
    else:
        summary["steps"]["append"] = {"status": "skipped" if args.skip_append else "blocked"}

    if not fatal_error and not args.skip_panel:
        if args.dry_run:
            write_wrapper_do(wrapper_panel, repo_root, "Do-files/03_Construct_panel_of_workers.do", extra_globals=do_globals)
            summary["steps"]["panel"] = {"status": "would_run", "wrapper_do": str(wrapper_panel)}
        else:
            write_wrapper_do(wrapper_panel, repo_root, "Do-files/03_Construct_panel_of_workers.do", extra_globals=do_globals)
            try:
                result = run_stata_do(args.stata_bin, wrapper_panel, args.timeout_seconds, cwd=repo_root)
                ok = result["returncode"] == 0 and expected_panel.exists()
                result["panel_output_exists"] = expected_panel.exists()
                result["panel_latest_exists"] = expected_panel_latest.exists()
                result["status"] = "ok" if ok else "failed"
                summary["steps"]["panel"] = result
                if not ok:
                    fatal_error = True
            except Exception as exc:  # noqa: BLE001
                summary["steps"]["panel"] = {"status": "failed", "error": str(exc)}
                fatal_error = True
    else:
        summary["steps"]["panel"] = {"status": "skipped" if args.skip_panel else "blocked"}

    if not fatal_error and args.run_qc:
        write_wrapper_do(wrapper_qc, repo_root, "Do-files/Quality_Checks/00_Run_All_Sequential.do")
        if args.dry_run:
            summary["steps"]["qc"] = {"status": "would_run", "wrapper_do": str(wrapper_qc)}
        else:
            try:
                result = run_stata_do(args.stata_bin, wrapper_qc, args.timeout_seconds, cwd=repo_root)
                result["status"] = "ok" if result["returncode"] == 0 else "failed"
                summary["steps"]["qc"] = result
                if result["status"] != "ok":
                    fatal_error = True
            except Exception as exc:  # noqa: BLE001
                summary["steps"]["qc"] = {"status": "failed", "error": str(exc)}
                fatal_error = True
    elif not args.run_qc:
        summary["steps"]["qc"] = {"status": "skipped"}

    summary["status"] = "failed" if fatal_error else "ok"
    if fatal_error:
        reason = extract_error_from_steps(summary["steps"])
        if reason:
            summary["error"] = reason
    write_json(summary_path, summary)

    print(f"Phase 2 run status: {summary['status']}")
    print(f"Summary: {summary_path}")
    for step_name in ("extract", "validate_inputs", "stata_preflight", "harmonization", "append", "panel", "qc"):
        step = summary["steps"].get(step_name, {})
        print(f"{step_name}: {step.get('status', 'n/a')}")
    if summary.get("error"):
        print(f"error: {summary['error']}", file=sys.stderr)

    return 1 if fatal_error else 0


if __name__ == "__main__":
    raise SystemExit(main())
