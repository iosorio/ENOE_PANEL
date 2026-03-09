#!/usr/bin/env python3
"""Diagnose ENOE pipeline failures from state JSON or log files."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from validate_repo import resolve_repo_root


LICENSE_PATTERNS = (
    (re.compile(r"\blicense\s+has\s+expired\b", re.I), "Stata license has expired."),
    (re.compile(r"\bexpired\s+license\b", re.I), "Stata license has expired."),
    (re.compile(r"\bno\s+valid\s+license\b", re.I), "No valid Stata license was found."),
    (re.compile(r"\bnot\s+licensed\b", re.I), "The Stata binary is not licensed."),
    (
        re.compile(r"\blicense\s+file\b.{0,80}\b(not\s+found|cannot|could\s+not|invalid|error)\b", re.I),
        "The Stata license file is missing or invalid.",
    ),
)

PERMISSION_PATTERNS = (
    (re.compile(r"operation not permitted", re.I), "Filesystem or sandbox permission blocked the operation."),
    (re.compile(r"permission denied", re.I), "Filesystem permission denied."),
)

PATH_PATTERNS = (
    (re.compile(r"missing poverty lines csv", re.I), "The poverty-line CSV was not found."),
    (re.compile(r"original dir missing", re.I), "The quarter Original directory is missing."),
    (re.compile(r"no zip found", re.I), "The expected quarter ZIP was not found."),
    (re.compile(r"no such file or directory", re.I), "A required file or directory was not found."),
    (re.compile(r"could not determine target quarter", re.I), "Phase 1 state did not provide a target quarter."),
    (re.compile(r"cannot read harmonized file", re.I), "Append/panel step could not read a harmonized file."),
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Diagnose ENOE pipeline failures from JSON summaries or logs")
    ap.add_argument("--cwd", default=None, help="Starting directory for repo discovery")
    ap.add_argument("--repo-root", default=None, help="Explicit ENOE_PANEL repo root override")
    ap.add_argument("--path", default=None, help="Optional artifact path to inspect; defaults to latest known artifact")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return ap.parse_args()


def emit(payload: dict[str, object], pretty: bool) -> None:
    indent = 2 if pretty else None
    print(json.dumps(payload, ensure_ascii=True, indent=indent))


def require_repo_root(args: argparse.Namespace) -> Path:
    repo_root, payload = resolve_repo_root(args.cwd, args.repo_root)
    if repo_root is None:
        emit(payload, True)
        raise SystemExit(2)
    return repo_root


def latest_known_artifact(repo_root: Path) -> Path | None:
    patterns = (
        "Do-files/quarterly_agent/state/runs/*.json",
        "Do-files/quarterly_agent/state/rebuild_parallel/*.json",
        "Do-files/quarterly_agent/state/agent_runs/*.json",
        "Do-files/Logs/**/*.log",
        "tmp_*.log",
    )
    candidates: list[Path] = []
    for pattern in patterns:
        candidates.extend(path for path in repo_root.glob(pattern) if path.is_file())
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def load_artifact(path: Path) -> tuple[str, object]:
    if path.suffix.lower() == ".json":
        return "json", json.loads(path.read_text(encoding="utf-8", errors="replace"))
    return "text", path.read_text(encoding="utf-8", errors="replace")


def summarize_text(raw: str, max_chars: int = 240) -> str:
    text = " ".join(raw.split())
    return text[:max_chars]


def extract_text(payload: object) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        chunks: list[str] = []
        for value in payload.values():
            chunks.append(extract_text(value))
        return "\n".join(chunks)
    if isinstance(payload, list):
        return "\n".join(extract_text(item) for item in payload)
    return str(payload)


def find_step_with_diagnostic(payload: dict[str, object]) -> tuple[str, dict[str, object]] | None:
    steps = payload.get("steps")
    if not isinstance(steps, dict):
        return None
    for step_name in ("onedrive_gate", "stata_preflight", "harmonization", "append", "panel", "qc"):
        step = steps.get(step_name)
        if isinstance(step, dict):
            diagnostic = step.get("diagnostic")
            if isinstance(diagnostic, dict):
                return step_name, diagnostic
    return None


def classify_known_failure(text: str) -> tuple[str, str, str] | None:
    lowered = text.lower()

    if "onedrive gate not satisfied" in lowered or "missing_ack_file" in lowered or "stale_ack_file" in lowered:
        return (
            "onedrive_gate",
            "Parallel rebuild is blocked by the OneDrive pause gate.",
            "Pause OneDrive sync and refresh Do-files/quarterly_agent/state/locks/onedrive_paused.ok before rerunning.",
        )

    for pattern, message in LICENSE_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("license", message, "Renew or reconfigure the Stata license, then rerun the failed step.")

    if re.search(r"too many users|all in use", lowered):
        return (
            "license_seat",
            "All Stata license seats are in use.",
            "Wait for a free seat or use a different Stata license target.",
        )

    for pattern, message in PERMISSION_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("permission", message, "Check file permissions, cloud-sync locks, and shell access to the target path.")

    if re.search(r"r\(111\);", lowered) or re.search(r"variable\s+.+\s+not found", lowered):
        return (
            "missing_variable",
            "Stata reported r(111), usually a missing variable or wrong module-specific variable name.",
            "Inspect the referenced quarter do-file and the failing log section for variable-presence guards or renamed inputs.",
        )

    for pattern, message in PATH_PATTERNS:
        match = pattern.search(text)
        if match:
            return ("path_error", message, "Check repo paths, quarter folders, and required input files before rerunning.")

    binary_match = re.search(r"stata executable not found:\s*(.+)", text, re.I)
    if binary_match:
        return (
            "binary_not_found",
            f"Configured Stata binary was not found: {binary_match.group(1).strip()}",
            "Set --stata-bin to a valid executable path or add the binary to PATH.",
        )

    runtime_match = re.search(r"r\(([1-9][0-9]*)\);", lowered)
    if runtime_match:
        code = runtime_match.group(1)
        return (
            "stata_runtime_error",
            f"Stata runtime error r({code}) was detected.",
            "Inspect the associated log tail around the failing step and fix the underlying Stata error before rerunning.",
        )

    return None


def diagnose_json(path: Path, payload: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "ok",
        "artifact_path": str(path),
        "artifact_type": "json",
        "run_status": payload.get("status", ""),
    }

    onedrive_step = payload.get("steps", {}).get("onedrive_gate") if isinstance(payload.get("steps"), dict) else None
    if isinstance(onedrive_step, dict) and str(onedrive_step.get("status", "")).startswith("blocked"):
        check = onedrive_step.get("check", {})
        result.update(
            {
                "category": "onedrive_gate",
                "message": "Parallel rebuild is blocked by the OneDrive pause gate.",
                "suggested_fix": "Pause OneDrive sync and refresh Do-files/quarterly_agent/state/locks/onedrive_paused.ok.",
                "evidence": summarize_text(json.dumps(check, ensure_ascii=True)),
            }
        )
        return result

    step_with_diagnostic = find_step_with_diagnostic(payload)
    if step_with_diagnostic is not None:
        step_name, diagnostic = step_with_diagnostic
        category = str(diagnostic.get("category", "unknown"))
        message = str(diagnostic.get("message", "Structured diagnostic detected."))
        result.update(
            {
                "category": "missing_variable" if category == "stata_runtime_error" and "r(111)" in extract_text(payload).lower() else category,
                "message": message,
                "source_step": step_name,
            }
        )
        if result["category"] == "missing_variable":
            result["suggested_fix"] = "Inspect the failing log section for a missing variable or renamed quarter-specific field."
        return result

    text = extract_text(payload)
    match = classify_known_failure(text)
    if match is not None:
        category, message, suggested_fix = match
        result.update(
            {
                "category": category,
                "message": message,
                "suggested_fix": suggested_fix,
                "evidence": summarize_text(text),
            }
        )
        return result

    if str(payload.get("status", "")).lower() == "ok":
        result.update(
            {
                "category": "ok",
                "message": "The artifact indicates a successful run.",
                "suggested_fix": "",
            }
        )
        return result

    result.update(
        {
            "category": "unknown",
            "message": "No known failure pattern matched this JSON artifact.",
            "suggested_fix": "Inspect the referenced JSON steps and associated log_path fields manually.",
            "evidence": summarize_text(text),
        }
    )
    return result


def diagnose_text(path: Path, text: str) -> dict[str, object]:
    result: dict[str, object] = {
        "status": "ok",
        "artifact_path": str(path),
        "artifact_type": "text",
    }
    match = classify_known_failure(text)
    if match is not None:
        category, message, suggested_fix = match
        result.update(
            {
                "category": category,
                "message": message,
                "suggested_fix": suggested_fix,
                "evidence": summarize_text(text),
            }
        )
        return result

    result.update(
        {
            "category": "unknown",
            "message": "No known failure pattern matched this log artifact.",
            "suggested_fix": "Inspect the log manually around the first non-zero exit or error message.",
            "evidence": summarize_text(text),
        }
    )
    return result


def main() -> int:
    args = parse_args()
    repo_root = require_repo_root(args)
    artifact = Path(args.path).expanduser().resolve() if args.path else latest_known_artifact(repo_root)

    if artifact is None:
        payload = {
            "status": "error",
            "message": "No ENOE run artifact was found to diagnose.",
            "repo_root": str(repo_root),
        }
        emit(payload, args.pretty)
        return 2

    kind, loaded = load_artifact(artifact)
    if kind == "json":
        payload = diagnose_json(artifact, loaded)
    else:
        payload = diagnose_text(artifact, loaded)
    emit(payload, args.pretty)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

