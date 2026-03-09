#!/usr/bin/env python3
"""Resolve and validate the ENOE_PANEL repository root."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


REQUIRED_RELATIVE_PATHS = (
    Path("Do-files/00_Master.do"),
    Path("Do-files/quarterly_agent/run_quarterly_agent.py"),
    Path("Do-files/quarterly_agent/phase2_rebuild_range_parallel.py"),
    Path("Do-files/quality_checks_py/qcheck_harmonization.py"),
    Path("README.md"),
)


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Validate ENOE_PANEL repo root from cwd or ENOE_REPO_ROOT")
    ap.add_argument("--cwd", default=None, help="Starting directory to inspect; defaults to current working directory")
    ap.add_argument(
        "--repo-root",
        default=os.environ.get("ENOE_REPO_ROOT"),
        help="Optional ENOE_PANEL repo root override; falls back to ENOE_REPO_ROOT",
    )
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    return ap.parse_args()


def is_repo_root(path: Path) -> bool:
    return all((path / rel).exists() for rel in REQUIRED_RELATIVE_PATHS)


def iter_candidate_roots(start: Path) -> list[Path]:
    return [start, *start.parents]


def normalize_path(raw: str | Path | None) -> Path | None:
    if raw in (None, ""):
        return None
    return Path(raw).expanduser().resolve()


def success_payload(repo_root: Path, source: str, cwd: Path, checked: list[str]) -> dict[str, object]:
    return {
        "status": "ok",
        "repo_root": str(repo_root),
        "cwd": str(cwd),
        "resolution_source": source,
        "checked_paths": checked,
        "required_paths": [str(rel) for rel in REQUIRED_RELATIVE_PATHS],
    }


def error_payload(message: str, cwd: Path, checked: list[str], override: Path | None) -> dict[str, object]:
    return {
        "status": "error",
        "message": message,
        "cwd": str(cwd),
        "checked_paths": checked,
        "override_path": str(override) if override else "",
        "required_paths": [str(rel) for rel in REQUIRED_RELATIVE_PATHS],
    }


def resolve_repo_root(
    cwd: str | Path | None = None,
    override: str | Path | None = None,
) -> tuple[Path | None, dict[str, object]]:
    start = normalize_path(cwd) or Path.cwd().resolve()
    override_path = normalize_path(override)

    checked: list[str] = []
    seen: set[str] = set()

    for candidate in iter_candidate_roots(start):
        label = str(candidate)
        if label in seen:
            continue
        seen.add(label)
        checked.append(label)
        if is_repo_root(candidate):
            return candidate, success_payload(candidate, "cwd", start, checked)

    if override_path is not None:
        label = str(override_path)
        if label not in seen:
            checked.append(label)
        if is_repo_root(override_path):
            return override_path, success_payload(override_path, "override", start, checked)
        return None, error_payload("Override path is not a valid ENOE_PANEL repo root.", start, checked, override_path)

    return None, error_payload("Could not resolve ENOE_PANEL repo root from cwd or ENOE_REPO_ROOT.", start, checked, None)


def emit(payload: dict[str, object], pretty: bool) -> None:
    indent = 2 if pretty else None
    print(json.dumps(payload, ensure_ascii=True, indent=indent))


def main() -> int:
    args = parse_args()
    repo_root, payload = resolve_repo_root(args.cwd, args.repo_root)
    emit(payload, args.pretty)
    return 0 if repo_root is not None else 2


if __name__ == "__main__":
    raise SystemExit(main())

