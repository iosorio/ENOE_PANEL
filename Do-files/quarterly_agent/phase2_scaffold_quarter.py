#!/usr/bin/env python3
"""Phase 2A: scaffold a new ENOE quarter folder and patch harmonization do-file."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from versioning import (
    ENOEVersionConfig,
    harm_dir as cfg_harm_dir,
    harm_program_path as cfg_harm_program_path,
    load_version_config,
    master_dir as cfg_master_dir,
    quarter_root as cfg_quarter_root,
    resolve_existing_harm_dir,
    resolve_existing_master_dir,
)


@dataclass(frozen=True)
class QuarterRef:
    year: int
    quarter: int

    @property
    def label(self) -> str:
        return f"{self.year}-Q{self.quarter}"


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_state = default_repo / "Do-files" / "quarterly_agent" / "state" / "inegi_enoe_phase1_state.json"
    default_out = default_repo / "Do-files" / "quarterly_agent" / "state" / "phase2_scaffold_last.json"

    ap = argparse.ArgumentParser(description="Scaffold new ENOE quarter from existing quarter template")
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--state-file", default=str(default_state))
    ap.add_argument("--state-out", default=str(default_out))
    ap.add_argument("--target-year", type=int, default=None)
    ap.add_argument("--target-quarter", type=int, choices=[1, 2, 3, 4], default=None)
    ap.add_argument("--source-year", type=int, default=None)
    ap.add_argument("--source-quarter", type=int, choices=[1, 2, 3, 4], default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--force", action="store_true", help="Recreate target folder if it exists")
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


def quarter_root(repo_root: Path, cfg: ENOEVersionConfig, ref: QuarterRef) -> Path:
    return cfg_quarter_root(repo_root, cfg, ref.year, ref.quarter)


def master_dir(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return cfg_master_dir(root, cfg, year)


def harm_dir(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return cfg_harm_dir(root, cfg, year)


def harm_program_path(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return cfg_harm_program_path(root, cfg, year)


def list_existing_quarters(repo_root: Path) -> list[QuarterRef]:
    out: list[QuarterRef] = []
    pattern = re.compile(r"^MEX_(\d{4})_ENOE-Q([1-4])$")
    for child in repo_root.iterdir():
        if not child.is_dir():
            continue
        m = pattern.match(child.name)
        if m:
            out.append(QuarterRef(int(m.group(1)), int(m.group(2))))
    return sorted(out, key=lambda q: (q.year, q.quarter))


def prev_quarter(ref: QuarterRef) -> QuarterRef:
    if ref.quarter > 1:
        return QuarterRef(ref.year, ref.quarter - 1)
    return QuarterRef(ref.year - 1, 4)


def choose_target_from_phase1_state(state: dict[str, Any]) -> QuarterRef | None:
    records = state.get("remote_records", {})
    if not isinstance(records, dict):
        return None
    candidates: list[QuarterRef] = []
    for payload in records.values():
        if not isinstance(payload, dict):
            continue
        try:
            yy = int(payload.get("year"))
            qq = int(payload.get("quarter"))
        except (TypeError, ValueError):
            continue
        if qq not in (1, 2, 3, 4):
            continue
        candidates.append(QuarterRef(yy, qq))
    if not candidates:
        return None
    return sorted(candidates, key=lambda q: (q.year, q.quarter))[-1]


def find_fallback_source(repo_root: Path, target: QuarterRef) -> QuarterRef | None:
    existing = list_existing_quarters(repo_root)
    earlier = [q for q in existing if (q.year, q.quarter) < (target.year, target.quarter)]
    if not earlier:
        return None
    return earlier[-1]


def patch_harmonization_do(do_path: Path, cfg: ENOEVersionConfig, target: QuarterRef) -> dict[str, int]:
    text = do_path.read_text(encoding="utf-8", errors="replace")
    replacements = 0

    def subn(pattern: str, repl: str, source: str) -> tuple[str, int]:
        return re.subn(pattern, repl, source, flags=re.MULTILINE)

    text, n = subn(r'local\s+year\s+"[0-9]{4}"', f'local year    "{target.year}"', text)
    replacements += n
    text, n = subn(r'local\s+vermast\s+"V[0-9]{2}"', f'local vermast "{cfg.raw_version}"', text)
    replacements += n
    text, n = subn(r'local\s+veralt\s+"V[0-9]{2}"', f'local veralt  "{cfg.harm_version}"', text)
    replacements += n
    text, n = subn(r'local\s+quarter\s+"Q[1-4]"', f'local quarter "Q{target.quarter}"', text)
    replacements += n
    text, n = subn(r'gen\s+wave\s*=\s*"Q[1-4]"', f'gen wave = "Q{target.quarter}"', text)
    replacements += n
    text, n = subn(r'(<_Survey Year_>\s*\[)[0-9]{4}(\]\s*</_Survey Year_>)', rf"\g<1>{target.year}\2", text)
    replacements += n

    if target.quarter == 1:
        text, n = subn(r"\bp3l\s*==", "p3q==", text)
        replacements += n
    else:
        text, n = subn(r"\bp3q\s*==", "p3l==", text)
        replacements += n

    do_path.write_text(text, encoding="utf-8")
    return {"replacements": replacements}


def clear_harmonized_outputs(harm_data_dir: Path) -> list[str]:
    removed: list[str] = []
    if not harm_data_dir.exists():
        return removed
    for path in sorted(harm_data_dir.glob("*")):
        if path.is_file():
            path.unlink()
            removed.append(str(path))
    return removed


def keep_only_target_original_zips(original_dir: Path, target: QuarterRef) -> list[str]:
    removed: list[str] = []
    if not original_dir.exists():
        return removed

    keep = {
        f"original_MEX_{target.year}_ENOE-Q{target.quarter}.zip",
        f"original_MEX_{target.year}-Q{target.quarter}.zip",
    }
    for path in sorted(original_dir.glob("*.zip")):
        if path.name not in keep:
            path.unlink()
            removed.append(str(path))
    return removed


def clear_stata_quarter_files(stata_dir: Path) -> list[str]:
    removed: list[str] = []
    if not stata_dir.exists():
        return removed
    patt = re.compile(r"(?i)^(?:enoe_|enoen_)?(?:coe1t|coe2t|sdemt|hogt|vivt)\d{3}\.dta$")
    for path in sorted(stata_dir.glob("*.dta")):
        if patt.match(path.name):
            path.unlink()
            removed.append(str(path))
    return removed


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cfg = load_version_config(repo_root)
    state_file = Path(args.state_file).resolve()
    state_out = Path(args.state_out).resolve()

    phase1_state = read_json(state_file)
    target = None
    if args.target_year is not None and args.target_quarter is not None:
        target = QuarterRef(args.target_year, args.target_quarter)
    elif args.target_year is None and args.target_quarter is None:
        target = choose_target_from_phase1_state(phase1_state)
    else:
        print("ERROR: provide both --target-year and --target-quarter, or neither.", file=sys.stderr)
        return 2

    if target is None:
        print("ERROR: could not determine target quarter.", file=sys.stderr)
        return 2

    if args.source_year is not None and args.source_quarter is not None:
        source = QuarterRef(args.source_year, args.source_quarter)
    elif args.source_year is None and args.source_quarter is None:
        preferred = prev_quarter(target)
        source = preferred if quarter_root(repo_root, preferred).exists() else find_fallback_source(repo_root, target)
    else:
        print("ERROR: provide both --source-year and --source-quarter, or neither.", file=sys.stderr)
        return 2

    if source is None:
        print("ERROR: could not determine source quarter.", file=sys.stderr)
        return 2

    src_root = quarter_root(repo_root, cfg, source)
    dst_root = quarter_root(repo_root, cfg, target)
    if not src_root.exists():
        print(f"ERROR: source quarter does not exist: {src_root}", file=sys.stderr)
        return 2

    exists_before = dst_root.exists()
    action = "none"
    if exists_before and not args.force:
        action = "skipped_target_exists"
    elif args.dry_run:
        action = "would_scaffold"
    else:
        if exists_before and args.force:
            shutil.rmtree(dst_root)
        shutil.copytree(src_root, dst_root)
        action = "scaffolded"

    changes: dict[str, Any] = {
        "action": action,
        "source": source.label,
        "target": target.label,
        "repo_root": str(repo_root),
        "target_exists_before": exists_before,
        "files_removed": {"original": [], "stata": [], "harmonized": []},
        "patched_do": "",
    }

    if action == "scaffolded":
        old_master = resolve_existing_master_dir(dst_root, cfg, source.year)
        new_master = master_dir(dst_root, cfg, target.year)
        old_harm = resolve_existing_harm_dir(dst_root, cfg, source.year)
        new_harm = harm_dir(dst_root, cfg, target.year)

        if old_master is not None and old_master.exists() and old_master != new_master:
            old_master.rename(new_master)
        if old_harm is not None and old_harm.exists() and old_harm != new_harm:
            old_harm.rename(new_harm)

        programs_dir = new_harm / "Programs"
        new_do = harm_program_path(dst_root, cfg, target.year)
        old_do_candidates = sorted(programs_dir.glob(f"{cfg.country}_{source.year}_{cfg.survey}_*_ALL.do"))
        if old_do_candidates:
            old_do = old_do_candidates[0]
            if old_do != new_do:
                old_do.rename(new_do)

        if not new_do.exists():
            print(f"ERROR: harmonization do-file not found: {new_do}", file=sys.stderr)
            return 2

        patch_info = patch_harmonization_do(new_do, cfg, target)
        changes["patched_do"] = str(new_do)
        changes["patch_info"] = patch_info

        original_dir = new_master / "Data" / "Original"
        stata_dir = new_master / "Data" / "Stata"
        harm_data_dir = new_harm / "Data" / "Harmonized"

        changes["files_removed"]["original"] = keep_only_target_original_zips(original_dir, target)
        changes["files_removed"]["stata"] = clear_stata_quarter_files(stata_dir)
        changes["files_removed"]["harmonized"] = clear_harmonized_outputs(harm_data_dir)

    payload = {
        "version": 1,
        "timestamp_utc": utc_now_iso(),
        "dry_run": args.dry_run,
        "force": args.force,
        "changes": changes,
    }
    write_json(state_out, payload)

    print(f"Phase 2 scaffold complete: action={action} source={source.label} target={target.label}")
    print(f"State written to: {state_out}")
    if args.verbose:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
