#!/usr/bin/env python3
"""Prepare a new local ENOE harmonization lineage from one A-version to another."""

from __future__ import annotations

import argparse
import shutil
import json
import re
from pathlib import Path
from typing import Any

from versioning import ENOEVersionConfig, load_version_config


QUARTER_ROOT_RE = re.compile(r"^(?P<country>[A-Z]{3})_(?P<year>\d{4})_(?P<survey>[A-Z0-9]+)-Q(?P<quarter>[1-4])$")


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo = script.parents[2]
    default_out = default_repo / "Do-files" / "quarterly_agent" / "state" / "harm_version_bump_last.json"

    ap = argparse.ArgumentParser(
        description="Prepare a new local ENOE harmonization version while preserving prior versioned outputs by default"
    )
    ap.add_argument("--repo-root", default=str(default_repo))
    ap.add_argument("--to-harm-version", required=True, help="Target harmonization version token, for example V07")
    ap.add_argument("--from-harm-version", default=None, help="Current local harmonization version token, defaults to manifest")
    ap.add_argument("--state-out", default=str(default_out))
    ap.add_argument(
        "--mode",
        choices=["scaffold", "rename"],
        default="scaffold",
        help="scaffold = preserve old version and create a new version tree; rename = destructive in-place migration",
    )
    ap.add_argument(
        "--copy-harmonized-data",
        action="store_true",
        help="With --mode scaffold, copy Data/Harmonized files into the new version tree. Off by default to avoid stale derived outputs.",
    )
    ap.add_argument(
        "--copy-logs",
        action="store_true",
        help="With --mode scaffold, copy existing program log files into the new version tree. Off by default.",
    )
    ap.add_argument("--dry-run", action="store_true")
    return ap.parse_args()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=True, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def replace_harm_version_tag(tag: str, from_harm_version: str, to_harm_version: str) -> str:
    needle = f"_{from_harm_version}_A_"
    if needle not in tag:
        raise ValueError(f"Could not find {needle} in tag {tag}")
    return tag.replace(needle, f"_{to_harm_version}_A_", 1)


def rename_path(path: Path, new_path: Path, dry_run: bool, changes: list[dict[str, str]]) -> None:
    if path == new_path or not path.exists():
        return
    changes.append({"from": str(path), "to": str(new_path)})
    if not dry_run:
        new_path.parent.mkdir(parents=True, exist_ok=True)
        path.rename(new_path)


def copy_file(
    source: Path,
    target: Path,
    dry_run: bool,
    changes: list[dict[str, str]],
    *,
    rewrite_text: tuple[str, str] | None = None,
) -> None:
    if not source.exists():
        return
    changes.append({"from": str(source), "to": str(target), "action": "copy"})
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if rewrite_text is None:
        shutil.copy2(source, target)
        return
    old_tag, new_tag = rewrite_text
    text = source.read_text(encoding="utf-8", errors="replace")
    target.write_text(text.replace(old_tag, new_tag), encoding="utf-8")


def rename_tagged_files(root: Path, old_tag: str, new_tag: str, dry_run: bool, changes: list[dict[str, str]]) -> None:
    if not root.exists():
        return
    tagged_files = sorted(
        [path for path in root.rglob(f"*{old_tag}*") if path.is_file()],
        key=lambda path: len(path.parts),
        reverse=True,
    )
    for path in tagged_files:
        new_name = path.name.replace(old_tag, new_tag)
        rename_path(path, path.with_name(new_name), dry_run, changes)


def ensure_dir(path: Path, dry_run: bool, changes: list[dict[str, str]]) -> None:
    changes.append({"from": "", "to": str(path), "action": "mkdir"})
    if not dry_run:
        path.mkdir(parents=True, exist_ok=True)


def scaffold_quarter(
    qroot: Path,
    cfg: ENOEVersionConfig,
    from_harm_version: str,
    to_harm_version: str,
    dry_run: bool,
    copy_harmonized_data: bool,
    copy_logs: bool,
) -> dict[str, Any]:
    old_tag = f"{cfg.raw_version}_M_{from_harm_version}_A_{cfg.harmonization_acronym}"
    new_tag = f"{cfg.raw_version}_M_{to_harm_version}_A_{cfg.harmonization_acronym}"
    changes: list[dict[str, str]] = []

    year = qroot.name.split("_")[1]
    old_dir = qroot / f"{cfg.country}_{year}_{cfg.survey}_{old_tag}"
    new_dir = qroot / f"{cfg.country}_{year}_{cfg.survey}_{new_tag}"

    if not old_dir.exists():
        return {"quarter_root": str(qroot), "status": "skipped_missing_old_dir", "changes": changes}
    if new_dir.exists():
        return {"quarter_root": str(qroot), "status": "skipped_existing_new_dir", "changes": changes}

    ensure_dir(new_dir, dry_run, changes)
    ensure_dir(new_dir / "Programs", dry_run, changes)
    ensure_dir(new_dir / "Data", dry_run, changes)
    ensure_dir(new_dir / "Data" / "Additional Data", dry_run, changes)
    ensure_dir(new_dir / "Data" / "Harmonized", dry_run, changes)

    programs_dir = old_dir / "Programs"
    if programs_dir.exists():
        for source in sorted(programs_dir.rglob("*")):
            if not source.is_file():
                continue
            if source.name == ".DS_Store":
                continue
            if source.suffix.lower() == ".log" and not copy_logs:
                continue
            rel = source.relative_to(programs_dir)
            target_name = rel.name.replace(old_tag, new_tag)
            target = new_dir / "Programs" / rel.parent / target_name
            rewrite = (old_tag, new_tag) if source.suffix.lower() in {".do", ".ado", ".txt", ".md"} else None
            copy_file(source, target, dry_run, changes, rewrite_text=rewrite)

    addl_dir = old_dir / "Data" / "Additional Data"
    if addl_dir.exists():
        for source in sorted(addl_dir.rglob("*")):
            if not source.is_file():
                continue
            if source.name == ".DS_Store":
                continue
            rel = source.relative_to(addl_dir)
            target_name = rel.name.replace(old_tag, new_tag)
            target = new_dir / "Data" / "Additional Data" / rel.parent / target_name
            rewrite = (old_tag, new_tag) if source.suffix.lower() in {".do", ".ado", ".txt", ".md", ".csv"} else None
            copy_file(source, target, dry_run, changes, rewrite_text=rewrite)

    if copy_harmonized_data:
        harmonized_dir = old_dir / "Data" / "Harmonized"
        if harmonized_dir.exists():
            for source in sorted(harmonized_dir.rglob("*")):
                if not source.is_file():
                    continue
                if source.name == ".DS_Store":
                    continue
                rel = source.relative_to(harmonized_dir)
                target_name = rel.name.replace(old_tag, new_tag)
                target = new_dir / "Data" / "Harmonized" / rel.parent / target_name
                copy_file(source, target, dry_run, changes)

    return {"quarter_root": str(qroot), "status": "scaffolded" if changes else "unchanged", "changes": changes}


def update_manifest_harm_version(
    manifest_path: Path,
    from_harm_version: str,
    to_harm_version: str,
    dry_run: bool,
) -> dict[str, Any]:
    text = manifest_path.read_text(encoding="utf-8", errors="replace")
    updated = re.sub(
        r'(^if "\$\{enoe_harm_version\}" == "" global enoe_harm_version ")[^"]+(")',
        rf"\g<1>{to_harm_version}\2",
        text,
        count=1,
        flags=re.MULTILINE,
    )
    updated = re.sub(
        r"(\*   2\. Bump harmonization version \(for example )V\d{2}_A -> V\d{2}_A(\) only when there)",
        rf"\g<1>{from_harm_version}_A -> {to_harm_version}_A\2",
        updated,
        count=1,
    )
    updated = updated.replace(f"_{from_harm_version}_A_", f"_{to_harm_version}_A_")
    updated = updated.replace(f"{from_harm_version}_A =", f"{to_harm_version}_A =")
    status = "unchanged" if updated == text else ("would_update" if dry_run else "updated")
    if status == "updated":
        manifest_path.write_text(updated, encoding="utf-8")
    return {
        "path": str(manifest_path),
        "status": status,
        "from_harm_version": from_harm_version,
        "to_harm_version": to_harm_version,
    }


def quarter_roots(repo_root: Path, cfg: ENOEVersionConfig) -> list[Path]:
    out: list[Path] = []
    for child in repo_root.iterdir():
        if not child.is_dir():
            continue
        match = QUARTER_ROOT_RE.match(child.name)
        if not match:
            continue
        if match.group("country") != cfg.country or match.group("survey") != cfg.survey:
            continue
        out.append(child)
    return sorted(out)


def migrate_quarter(
    qroot: Path,
    cfg: ENOEVersionConfig,
    from_harm_version: str,
    to_harm_version: str,
    dry_run: bool,
) -> dict[str, Any]:
    old_tag = f"{cfg.raw_version}_M_{from_harm_version}_A_{cfg.harmonization_acronym}"
    new_tag = f"{cfg.raw_version}_M_{to_harm_version}_A_{cfg.harmonization_acronym}"
    changes: list[dict[str, str]] = []

    old_dir = qroot / f"{cfg.country}_{qroot.name.split('_')[1]}_{cfg.survey}_{old_tag}"
    new_dir = qroot / f"{cfg.country}_{qroot.name.split('_')[1]}_{cfg.survey}_{new_tag}"

    if not old_dir.exists():
        return {"quarter_root": str(qroot), "status": "skipped_missing_old_dir", "changes": changes}

    rename_tagged_files(old_dir, old_tag, new_tag, dry_run, changes)
    rename_path(old_dir, new_dir, dry_run, changes)
    return {"quarter_root": str(qroot), "status": "renamed" if changes else "unchanged", "changes": changes}


def migrate_panel_outputs(
    repo_root: Path,
    cfg: ENOEVersionConfig,
    from_harm_version: str,
    to_harm_version: str,
    dry_run: bool,
) -> dict[str, Any]:
    panel_root = repo_root / "PANEL" / "DATA"
    old_tag = f"{cfg.raw_version}_M_{from_harm_version}_A_{cfg.harmonization_acronym}"
    new_tag = f"{cfg.raw_version}_M_{to_harm_version}_A_{cfg.harmonization_acronym}"
    changes: list[dict[str, str]] = []
    if panel_root.exists():
        for path in sorted(panel_root.glob(f"*{old_tag}*.dta")):
            rename_path(path, path.with_name(path.name.replace(old_tag, new_tag)), dry_run, changes)
    return {"panel_root": str(panel_root), "status": "renamed" if changes else "unchanged", "changes": changes}


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    cfg = load_version_config(repo_root)
    from_harm_version = args.from_harm_version or cfg.harm_version
    to_harm_version = args.to_harm_version

    if from_harm_version == to_harm_version:
        raise SystemExit("from and to harmonization versions are identical")

    quarter_roots_list = quarter_roots(repo_root, cfg)
    if args.mode == "scaffold":
        old_tag = f"{cfg.raw_version}_M_{from_harm_version}_A_{cfg.harmonization_acronym}"
        new_tag = f"{cfg.raw_version}_M_{to_harm_version}_A_{cfg.harmonization_acronym}"
        existing_targets = [
            str(qroot / f"{cfg.country}_{qroot.name.split('_')[1]}_{cfg.survey}_{new_tag}")
            for qroot in quarter_roots_list
            if (qroot / f"{cfg.country}_{qroot.name.split('_')[1]}_{cfg.survey}_{new_tag}").exists()
        ]
        if existing_targets:
            raise SystemExit(
                "Target harmonization folders already exist; refusing to advance the manifest in scaffold mode:\n"
                + "\n".join(existing_targets)
            )

    if args.mode == "scaffold":
        quarter_results = [
            scaffold_quarter(
                qroot,
                cfg,
                from_harm_version,
                to_harm_version,
                args.dry_run,
                args.copy_harmonized_data,
                args.copy_logs,
            )
            for qroot in quarter_roots_list
        ]
        panel_result = {
            "panel_root": str(repo_root / "PANEL" / "DATA"),
            "status": "preserved",
            "changes": [],
            "note": "Existing versioned panel outputs were left in place. New outputs should be generated by rerunning the pipeline under the new manifest version.",
        }
    else:
        quarter_results = [
            migrate_quarter(qroot, cfg, from_harm_version, to_harm_version, args.dry_run)
            for qroot in quarter_roots_list
        ]
        panel_result = migrate_panel_outputs(repo_root, cfg, from_harm_version, to_harm_version, args.dry_run)
    manifest_result = update_manifest_harm_version(
        repo_root / "Do-files" / "00_ENOE_Versioning.do",
        from_harm_version,
        to_harm_version,
        args.dry_run,
    )

    summary = {
        "repo_root": str(repo_root),
        "dry_run": args.dry_run,
        "mode": args.mode,
        "from_harm_version": from_harm_version,
        "to_harm_version": to_harm_version,
        "quarters_touched": sum(1 for item in quarter_results if item["status"] in {"renamed", "scaffolded"}),
        "quarter_results": quarter_results,
        "panel_result": panel_result,
        "manifest_result": manifest_result,
    }
    write_json(Path(args.state_out).resolve(), summary)
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
