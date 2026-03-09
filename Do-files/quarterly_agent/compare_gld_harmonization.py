#!/usr/bin/env python3
"""Compare a local ENOE harmonization do-file against the upstream World Bank GLD version."""

from __future__ import annotations

import argparse
import datetime as dt
import difflib
import json
import subprocess
from pathlib import Path
from typing import Any

from versioning import ENOEVersionConfig, harm_program_path, load_version_config, quarter_root


IGNORED_LINE_PREFIXES = (
    "<_Program name_>",
    "<_Date created_>",
    "<_Sample size (HH)_>",
    "<_Sample size (IND)_>",
)

IGNORED_SUBSTRINGS = (
    'if c(os)=="Windows" local server',
    'if c(os)=="MacOSX"|c(os)=="Unix"  local server',
)


def timestamp_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_out = default_repo / "Do-files" / "quarterly_agent" / "state" / "upstream_diff"
    default_clone = Path("/tmp/gld-upstream")
    ap = argparse.ArgumentParser(description="Compare local ENOE harmonization do-file against upstream GLD/MEX")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--quarter", type=int, default=None, choices=[1, 2, 3, 4])
    ap.add_argument("--upstream-root", default=str(default_clone))
    ap.add_argument("--upstream-ref", default="main")
    ap.add_argument("--fetch-upstream", action="store_true")
    ap.add_argument("--upstream-raw-version", default=None)
    ap.add_argument("--upstream-harm-version", default=None)
    ap.add_argument("--out-dir", default=str(default_out))
    ap.add_argument("--raw-diff", action="store_true", help="Keep metadata/server lines in the diff")
    return ap.parse_args()


def ensure_upstream(path: Path, repo_url: str, ref: str, fetch: bool) -> None:
    if path.exists() and not fetch:
        return
    if path.exists():
        subprocess.run(["git", "-C", str(path), "fetch", "--depth", "1", "origin", ref], check=True)
        subprocess.run(["git", "-C", str(path), "checkout", ref], check=True)
        subprocess.run(["git", "-C", str(path), "reset", "--hard", f"origin/{ref}"], check=True)
        return
    subprocess.run(["git", "clone", "--depth", "1", "--branch", ref, repo_url, str(path)], check=True)


def pick_local_quarter(repo_root: Path, cfg: ENOEVersionConfig, year: int, quarter: int | None) -> int:
    if quarter is not None:
        return quarter
    candidates = []
    for q in (1, 2, 3, 4):
        path = harm_program_path(quarter_root(repo_root, cfg, year, q), cfg, year)
        if path.exists():
            candidates.append(q)
    if not candidates:
        raise FileNotFoundError(f"No local harmonization do-file found for year {year}")
    return candidates[-1]


def upstream_program_path(
    upstream_root: Path,
    cfg: ENOEVersionConfig,
    year: int,
    raw_version: str,
    harm_version: str,
) -> Path:
    harm_tag = f"{raw_version}_M_{harm_version}_A_{cfg.harmonization_acronym}"
    stem = f"{cfg.country}_{year}_{cfg.survey}"
    return (
        upstream_root
        / "GLD"
        / cfg.country
        / stem
        / f"{stem}_{harm_tag}"
        / "Programs"
        / f"{stem}_{harm_tag}_ALL.do"
    )


def resolve_upstream_program_path(
    upstream_root: Path,
    cfg: ENOEVersionConfig,
    requested_year: int,
    raw_version: str,
    harm_version: str,
) -> tuple[Path, dict[str, Any]]:
    exact = upstream_program_path(upstream_root, cfg, requested_year, raw_version, harm_version)
    if exact.exists():
        return exact, {
            "requested_year": requested_year,
            "resolved_year": requested_year,
            "resolution": "exact_year",
        }

    search_root = upstream_root / "GLD" / cfg.country
    pattern = f"{cfg.country}_*_{cfg.survey}_{raw_version}_M_{harm_version}_A_{cfg.harmonization_acronym}_ALL.do"
    candidates: list[tuple[int, Path]] = []
    for path in search_root.rglob(pattern):
        parts = path.name.split("_")
        if len(parts) < 2:
            continue
        try:
            year = int(parts[1])
        except ValueError:
            continue
        candidates.append((year, path))

    if not candidates:
        raise FileNotFoundError(
            f"No upstream GLD do-file found for baseline {raw_version}_M_{harm_version}_A_{cfg.harmonization_acronym}"
        )

    candidates.sort(key=lambda item: item[0])
    resolved_year, resolved_path = candidates[-1]
    return resolved_path, {
        "requested_year": requested_year,
        "resolved_year": resolved_year,
        "resolution": "latest_available_year",
    }


def normalize_lines(text: str, raw_diff: bool) -> list[str]:
    lines = []
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not raw_diff:
            stripped = line.strip()
            if any(stripped.startswith(prefix) for prefix in IGNORED_LINE_PREFIXES):
                continue
            if any(token in line for token in IGNORED_SUBSTRINGS):
                continue
        lines.append(line + "\n")
    return lines


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cfg = load_version_config(repo_root)
    local_quarter = pick_local_quarter(repo_root, cfg, args.year, args.quarter)
    local_path = harm_program_path(quarter_root(repo_root, cfg, args.year, local_quarter), cfg, args.year)
    if not local_path.exists():
        raise FileNotFoundError(f"Local harmonization do-file not found: {local_path}")

    upstream_root = Path(args.upstream_root).resolve()
    ensure_upstream(upstream_root, cfg.upstream_repo, args.upstream_ref, args.fetch_upstream)

    upstream_raw = args.upstream_raw_version or cfg.upstream_compare_raw_version
    upstream_harm = args.upstream_harm_version or cfg.upstream_compare_harm_version
    upstream_path, upstream_resolution = resolve_upstream_program_path(
        upstream_root,
        cfg,
        args.year,
        upstream_raw,
        upstream_harm,
    )

    local_lines = normalize_lines(local_path.read_text(encoding="utf-8", errors="replace"), args.raw_diff)
    upstream_lines = normalize_lines(upstream_path.read_text(encoding="utf-8", errors="replace"), args.raw_diff)
    diff_lines = list(
        difflib.unified_diff(
            upstream_lines,
            local_lines,
            fromfile=str(upstream_path),
            tofile=str(local_path),
            lineterm="",
        )
    )

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = timestamp_slug()
    diff_path = out_dir / f"gld_compare_{args.year}Q{local_quarter}_{upstream_raw}_{upstream_harm}_{stamp}.patch"
    summary_path = out_dir / f"gld_compare_{args.year}Q{local_quarter}_{upstream_raw}_{upstream_harm}_{stamp}.json"
    diff_path.write_text("\n".join(diff_lines) + ("\n" if diff_lines else ""), encoding="utf-8")

    summary: dict[str, Any] = {
        "repo_root": str(repo_root),
        "local_year": args.year,
        "local_quarter": local_quarter,
        "local_path": str(local_path),
        "upstream_root": str(upstream_root),
        "upstream_ref": args.upstream_ref,
        "upstream_path": str(upstream_path),
        "upstream_resolution": upstream_resolution,
        "upstream_raw_version": upstream_raw,
        "upstream_harm_version": upstream_harm,
        "raw_diff": args.raw_diff,
        "diff_path": str(diff_path),
        "diff_line_count": len(diff_lines),
        "status": "different" if diff_lines else "identical",
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
