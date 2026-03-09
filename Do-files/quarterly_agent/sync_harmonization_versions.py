#!/usr/bin/env python3
"""Synchronize ENOE harmonization do-file headers with their file names."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

from versioning import load_version_config


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_out = default_repo / "Do-files" / "quarterly_agent" / "state" / "version_sync_last.json"
    ap = argparse.ArgumentParser(description="Sync harmonization do-file version headers to their file names")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--state-out", default=str(default_out))
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def patch_file(path: Path, dofile_re: re.Pattern[str], dry_run: bool) -> dict[str, Any]:
    match = dofile_re.match(path.name)
    if not match:
        return {"path": str(path), "status": "skipped_name"}

    year = match.group("year")
    raw = match.group("raw")
    harm = match.group("harm")
    expected_name = match.group(1)

    text = path.read_text(encoding="utf-8", errors="replace")
    original = text
    replacements = 0

    text, n = re.subn(
        r"(<_Program name_>\s*\[)[^\]]+(\]\s*</_Program name_>)",
        rf"\g<1>{expected_name}\2",
        text,
        count=1,
    )
    replacements += n
    text, n = re.subn(r'local\s+year\s+"[0-9]{4}"', f'local year    "{year}"', text, count=1)
    replacements += n
    text, n = re.subn(r'local\s+vermast\s+"V[0-9]{2}"', f'local vermast "{raw}"', text, count=1)
    replacements += n
    text, n = re.subn(r'local\s+veralt\s+"V[0-9]{2}"', f'local veralt  "{harm}"', text, count=1)
    replacements += n

    status = "unchanged" if text == original else ("would_update" if dry_run else "updated")
    if status == "updated":
        path.write_text(text, encoding="utf-8")

    return {
        "path": str(path),
        "status": status,
        "replacements": replacements,
        "expected_program_name": expected_name,
    }


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cfg = load_version_config(repo_root)
    dofile_re = re.compile(
        rf"^({cfg.country}_(?P<year>\d{{4}})_{cfg.survey}_(?P<raw>V\d{{2}})_M_(?P<harm>V\d{{2}})_A_{cfg.harmonization_acronym}_ALL\.do)$"
    )
    results = []
    for path in sorted(repo_root.rglob(f"{cfg.country}_*_{cfg.survey}_V*_M_V*_A_{cfg.harmonization_acronym}_ALL.do")):
        if "Programs" not in path.parts:
            continue
        results.append(patch_file(path, dofile_re, args.dry_run))

    summary = {
        "repo_root": str(repo_root),
        "dry_run": args.dry_run,
        "files_scanned": len(results),
        "files_changed": sum(1 for item in results if item["status"] in {"updated", "would_update"}),
        "results": results,
    }
    write_json(Path(args.state_out).resolve(), summary)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
