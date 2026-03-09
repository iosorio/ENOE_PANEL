#!/usr/bin/env python3
"""Phase 4: compare ENOE raw microdata schemas across quarters."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Any

from versioning import load_version_config, quarter_root, resolve_existing_master_dir

TABLE_TOKENS = ("COE1T", "COE2T", "SDEMT", "HOGT", "VIVT")
TABLE_RE = re.compile(r"(?i)^(?:enoe_|enoen_)?(coe1t|coe2t|sdemt|hogt|vivt)(\d{3})\.dta$")

KNOWN_RENAMES = {
    "ENT": "CVE_ENT",
    "MUN": "CVE_MUN",
    "LOC": "CVE_LOC",
    "AGEB": "CVE_AGEB",
}


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def timestamp_slug() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_out_dir = default_repo / "Do-files" / "quarterly_agent" / "state" / "schema"

    ap = argparse.ArgumentParser(description="Compare ENOE raw schema between two quarters")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--target-year", type=int, required=True)
    ap.add_argument("--target-quarter", type=int, choices=[1, 2, 3, 4], required=True)
    ap.add_argument("--base-year", type=int, default=None)
    ap.add_argument("--base-quarter", type=int, choices=[1, 2, 3, 4], default=None)
    ap.add_argument("--stata-bin", default="stata-mp")
    ap.add_argument("--timeout-seconds", type=int, default=120)
    ap.add_argument("--out-dir", default=str(default_out_dir))
    ap.add_argument("--fail-on-breaking", action="store_true")
    ap.add_argument("--comparison-tag", default="", help="Optional label appended to run/output id (e.g., prev, yoy)")
    ap.add_argument("--verbose", action="store_true")
    return ap.parse_args()


def quarter_suffix(year: int, quarter: int) -> str:
    return f"{quarter}{str(year)[2:]}"


def quarter_label(year: int, quarter: int) -> str:
    return f"{year}-Q{quarter}"


def prev_quarter(year: int, quarter: int) -> tuple[int, int]:
    if quarter > 1:
        return year, quarter - 1
    return year - 1, 4


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


def zip_for_quarter(repo_root: Path, year: int, quarter: int) -> Path:
    cfg = load_version_config(repo_root)
    root = quarter_root(repo_root, cfg, year, quarter)
    master = resolve_existing_master_dir(root, cfg, year)
    if master is None:
        raise FileNotFoundError(f"Master dir not found for {year}-Q{quarter}: {root}")
    original_dir = master / "Data" / "Original"
    if not original_dir.exists():
        raise FileNotFoundError(f"Original dir not found for {year}-Q{quarter}: {original_dir}")
    zip_path = choose_original_zip(original_dir, year, quarter)
    if zip_path is None:
        raise FileNotFoundError(f"No unique ZIP candidate for {year}-Q{quarter} in {original_dir}")
    return zip_path


def _stata_quote(path: Path) -> str:
    return str(path).replace('"', '""')


def inspect_dta_schema(dta_path: Path, stata_bin: str, timeout_seconds: int) -> dict[str, Any]:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        do_path = tmp / "schema_extract.do"
        out_path = tmp / "schema_cols.txt"
        do_content = (
            "clear\n"
            "set more off\n"
            f'use "{_stata_quote(dta_path)}", clear\n'
            f'file open fh using "{_stata_quote(out_path)}", write text replace\n'
            "foreach v of varlist _all {\n"
            "    local t : type `v'\n"
            "    file write fh \"`v'|`t'\" _n\n"
            "}\n"
            "file close fh\n"
            "exit 0\n"
        )
        do_path.write_text(do_content, encoding="utf-8")

        try:
            proc = subprocess.run(
                [stata_bin, "-b", "do", str(do_path)],
                cwd=tmp,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"Stata executable not found: {stata_bin}") from exc
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Stata schema extraction timed out ({timeout_seconds}s) for {dta_path}") from exc

        if proc.returncode != 0:
            tail = f"{proc.stdout[-2000:]}\n{proc.stderr[-2000:]}"
            raise RuntimeError(f"Stata schema extraction failed for {dta_path}. Tail:\n{tail}")
        if not out_path.exists():
            raise RuntimeError(f"Stata schema output not found for {dta_path}")

        cols: list[str] = []
        dtypes: dict[str, str] = {}
        for line in out_path.read_text(encoding="utf-8", errors="replace").splitlines():
            if "|" not in line:
                continue
            name, dtype = line.split("|", 1)
            col = name.strip().upper()
            dtypes[col] = dtype.strip()
            cols.append(col)

    return {
        "column_count": len(cols),
        "columns": cols,
        "dtypes": dtypes,
    }


def schema_from_zip(zip_path: Path, suffix: str, stata_bin: str, timeout_seconds: int) -> dict[str, dict[str, Any]]:
    by_token: dict[str, dict[str, Any]] = {}
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        with zipfile.ZipFile(zip_path, "r") as zf:
            members = sorted([m for m in zf.namelist() if m.lower().endswith(".dta")])
            for member in members:
                name = Path(member).name
                m = TABLE_RE.match(name)
                if not m:
                    continue
                token = m.group(1).upper()
                file_suffix = m.group(2)
                if token not in TABLE_TOKENS or file_suffix != suffix:
                    continue
                if token in by_token:
                    continue
                extracted = Path(zf.extract(member, path=tmp))
                schema = inspect_dta_schema(extracted, stata_bin=stata_bin, timeout_seconds=timeout_seconds)
                by_token[token] = {
                    "zip_member": member,
                    "file_name": name,
                    **schema,
                }
    return by_token


def compare_table(base: dict[str, Any], target: dict[str, Any]) -> dict[str, Any]:
    base_cols = set(base["columns"])
    target_cols = set(target["columns"])

    added = sorted(target_cols - base_cols)
    removed = sorted(base_cols - target_cols)
    common = sorted(base_cols & target_cols)

    type_changes: list[dict[str, str]] = []
    for col in common:
        b = base["dtypes"].get(col, "")
        t = target["dtypes"].get(col, "")
        if b != t:
            type_changes.append({"column": col, "base_dtype": b, "target_dtype": t})

    known_renames: list[dict[str, str]] = []
    for old, new in KNOWN_RENAMES.items():
        if old in removed and new in added:
            known_renames.append({"from": old, "to": new})

    renamed_from = {x["from"] for x in known_renames}
    renamed_to = {x["to"] for x in known_renames}
    unknown_removed = [c for c in removed if c not in renamed_from]
    unknown_added = [c for c in added if c not in renamed_to]

    status = "ok"
    if unknown_removed:
        status = "breaking"
    elif known_renames or unknown_added or type_changes:
        status = "changed"

    return {
        "status": status,
        "base_column_count": len(base["columns"]),
        "target_column_count": len(target["columns"]),
        "added": added,
        "removed": removed,
        "known_renames": known_renames,
        "unknown_added": unknown_added,
        "unknown_removed": unknown_removed,
        "type_changes": type_changes,
    }


def render_markdown_report(payload: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append(f"# Phase 4 Schema Diff: {payload['target']['label']}")
    lines.append("")
    lines.append(f"- Generated UTC: `{payload['timestamp_utc']}`")
    lines.append(f"- Base quarter: `{payload['base']['label']}`")
    lines.append(f"- Target quarter: `{payload['target']['label']}`")
    lines.append(f"- Overall status: `{payload['status']}`")
    lines.append("")

    for token in TABLE_TOKENS:
        table = payload["tables"].get(token, {})
        lines.append(f"## {token}")
        if "error" in table:
            lines.append(f"- Status: `missing`")
            lines.append(f"- Error: {table['error']}")
            lines.append("")
            continue

        lines.append(f"- Status: `{table['status']}`")
        lines.append(f"- Columns: `{table['base_column_count']} -> {table['target_column_count']}`")
        lines.append(f"- Added: `{len(table['added'])}`")
        lines.append(f"- Removed: `{len(table['removed'])}`")
        lines.append(f"- Type changes: `{len(table['type_changes'])}`")

        if table["known_renames"]:
            pairs = ", ".join(f"{x['from']}->{x['to']}" for x in table["known_renames"])
            lines.append(f"- Known renames detected: `{pairs}`")
        if table["unknown_removed"]:
            lines.append(f"- Unknown removed: `{', '.join(table['unknown_removed'])}`")
        if table["unknown_added"]:
            lines.append(f"- Unknown added: `{', '.join(table['unknown_added'])}`")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.base_year is not None and args.base_quarter is not None:
        base_year, base_quarter = args.base_year, args.base_quarter
    elif args.base_year is None and args.base_quarter is None:
        base_year, base_quarter = prev_quarter(args.target_year, args.target_quarter)
    else:
        print("ERROR: provide both --base-year and --base-quarter, or neither.", file=sys.stderr)
        return 2

    comp_tag = re.sub(r"[^A-Za-z0-9_-]+", "", args.comparison_tag.strip())
    if comp_tag:
        run_id = f"{args.target_year}Q{args.target_quarter}_{comp_tag}_{timestamp_slug()}"
    else:
        run_id = f"{args.target_year}Q{args.target_quarter}_{timestamp_slug()}"
    out_json = out_dir / f"phase4_schema_{run_id}.json"
    out_md = out_dir / f"phase4_schema_{run_id}.md"

    target_suffix = quarter_suffix(args.target_year, args.target_quarter)
    base_suffix = quarter_suffix(base_year, base_quarter)

    payload: dict[str, Any] = {
        "version": 1,
        "run_id": run_id,
        "timestamp_utc": utc_now_iso(),
        "comparison_tag": comp_tag,
        "base": {"year": base_year, "quarter": base_quarter, "label": quarter_label(base_year, base_quarter)},
        "target": {
            "year": args.target_year,
            "quarter": args.target_quarter,
            "label": quarter_label(args.target_year, args.target_quarter),
        },
        "paths": {},
        "status": "ok",
        "tables": {},
    }

    try:
        base_zip = zip_for_quarter(repo_root, base_year, base_quarter)
        target_zip = zip_for_quarter(repo_root, args.target_year, args.target_quarter)
    except FileNotFoundError as exc:
        payload["status"] = "error"
        payload["error"] = str(exc)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        out_md.write_text(render_markdown_report(payload), encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"JSON: {out_json}")
        print(f"MD: {out_md}")
        return 2

    payload["paths"]["base_zip"] = str(base_zip)
    payload["paths"]["target_zip"] = str(target_zip)

    try:
        base_schema = schema_from_zip(base_zip, base_suffix, stata_bin=args.stata_bin, timeout_seconds=args.timeout_seconds)
        target_schema = schema_from_zip(
            target_zip, target_suffix, stata_bin=args.stata_bin, timeout_seconds=args.timeout_seconds
        )
    except RuntimeError as exc:
        payload["status"] = "error"
        payload["error"] = str(exc)
        out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        out_md.write_text(render_markdown_report(payload), encoding="utf-8")
        print(f"ERROR: {exc}", file=sys.stderr)
        print(f"JSON: {out_json}")
        print(f"MD: {out_md}")
        return 2

    breaking = 0
    changed = 0

    for token in TABLE_TOKENS:
        base_table = base_schema.get(token)
        target_table = target_schema.get(token)

        if base_table is None or target_table is None:
            payload["tables"][token] = {
                "status": "breaking",
                "error": f"Missing table in {'base' if base_table is None else 'target'} ZIP",
            }
            breaking += 1
            continue

        diff = compare_table(base_table, target_table)
        payload["tables"][token] = diff
        if diff["status"] == "breaking":
            breaking += 1
        elif diff["status"] == "changed":
            changed += 1

    if breaking > 0:
        payload["status"] = "breaking"
    elif changed > 0:
        payload["status"] = "changed"
    else:
        payload["status"] = "ok"

    payload["summary"] = {
        "breaking_tables": breaking,
        "changed_tables": changed,
        "ok_tables": len(TABLE_TOKENS) - breaking - changed,
    }

    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    out_md.write_text(render_markdown_report(payload), encoding="utf-8")

    print(f"Phase 4 schema status: {payload['status']}")
    print(f"JSON: {out_json}")
    print(f"MD: {out_md}")
    for token in TABLE_TOKENS:
        status = payload["tables"].get(token, {}).get("status", "n/a")
        print(f"{token}: {status}")

    if args.verbose:
        print(json.dumps(payload, ensure_ascii=False, indent=2))

    if args.fail_on_breaking and payload["status"] == "breaking":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
