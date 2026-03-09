#!/usr/bin/env python3
"""Shared ENOE version manifest helpers for quarterly-agent utilities."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re


GLOBAL_RE = re.compile(r'\bglobal\s+(enoe_[A-Za-z0-9_]+)\s+"([^"]*)"')
VAR_REF_RE = re.compile(r"\$\{(enoe_[A-Za-z0-9_]+)\}")


@dataclass(frozen=True)
class ENOEVersionConfig:
    country: str
    survey: str
    raw_version: str
    harm_version: str
    harmonization_acronym: str
    raw_tag: str
    harm_tag: str
    upstream_compare_raw_version: str
    upstream_compare_harm_version: str
    upstream_compare_harm_tag: str
    upstream_repo: str

    def survey_stem(self, year: int) -> str:
        return f"{self.country}_{year}_{self.survey}"

    def quarter_root_name(self, year: int, quarter: int) -> str:
        return f"{self.survey_stem(year)}-Q{quarter}"

    def master_dir_name(self, year: int) -> str:
        return f"{self.survey_stem(year)}_{self.raw_tag}"

    def harm_dir_name(self, year: int) -> str:
        return f"{self.survey_stem(year)}_{self.harm_tag}"

    def harm_all_stem(self, year: int) -> str:
        return f"{self.survey_stem(year)}_{self.harm_tag}_ALL"

    def upstream_harm_tag(self) -> str:
        return self.upstream_compare_harm_tag

    def upstream_harm_dir_name(self, year: int) -> str:
        return f"{self.survey_stem(year)}_{self.upstream_harm_tag()}"

    def upstream_harm_all_stem(self, year: int) -> str:
        return f"{self.survey_stem(year)}_{self.upstream_harm_tag()}_ALL"


def version_manifest_path(repo_root: Path) -> Path:
    return repo_root / "Do-files" / "00_ENOE_Versioning.do"


def _parse_globals(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    text = path.read_text(encoding="utf-8", errors="replace")
    for line in text.splitlines():
        match = GLOBAL_RE.search(line)
        if match:
            values[match.group(1)] = match.group(2)
    return values


def _resolve_refs(values: dict[str, str]) -> dict[str, str]:
    resolved = dict(values)
    for _ in range(20):
        changed = False
        for key, value in list(resolved.items()):
            expanded = VAR_REF_RE.sub(lambda match: resolved.get(match.group(1), match.group(0)), value)
            if expanded != value:
                resolved[key] = expanded
                changed = True
        if not changed:
            break
    return resolved


def load_version_config(repo_root: Path) -> ENOEVersionConfig:
    manifest = version_manifest_path(repo_root)
    values = _resolve_refs(_parse_globals(manifest))
    required = (
        "enoe_country",
        "enoe_survey",
        "enoe_raw_version",
        "enoe_harm_version",
        "enoe_harmonization_acronym",
        "enoe_raw_tag",
        "enoe_harm_tag",
        "enoe_upcmp_raw_version",
        "enoe_upcmp_harm_version",
        "enoe_upcmp_harm_tag",
        "enoe_upcmp_repo",
    )
    missing = [key for key in required if key not in values or values[key] == ""]
    if missing:
        raise ValueError(f"Missing ENOE version globals in {manifest}: {', '.join(missing)}")

    return ENOEVersionConfig(
        country=values["enoe_country"],
        survey=values["enoe_survey"],
        raw_version=values["enoe_raw_version"],
        harm_version=values["enoe_harm_version"],
        harmonization_acronym=values["enoe_harmonization_acronym"],
        raw_tag=values["enoe_raw_tag"],
        harm_tag=values["enoe_harm_tag"],
        upstream_compare_raw_version=values["enoe_upcmp_raw_version"],
        upstream_compare_harm_version=values["enoe_upcmp_harm_version"],
        upstream_compare_harm_tag=values["enoe_upcmp_harm_tag"],
        upstream_repo=values["enoe_upcmp_repo"],
    )


def quarter_root(repo_root: Path, cfg: ENOEVersionConfig, year: int, quarter: int) -> Path:
    return repo_root / cfg.quarter_root_name(year, quarter)


def master_dir(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return root / cfg.master_dir_name(year)


def harm_dir(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return root / cfg.harm_dir_name(year)


def harm_program_path(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return harm_dir(root, cfg, year) / "Programs" / f"{cfg.harm_all_stem(year)}.do"


def harm_output_path(root: Path, cfg: ENOEVersionConfig, year: int) -> Path:
    return harm_dir(root, cfg, year) / "Data" / "Harmonized" / f"{cfg.harm_all_stem(year)}.dta"


def fullsample_output_path(repo_root: Path, cfg: ENOEVersionConfig, start_year: int, end_year: int, end_quarter: int) -> Path:
    tag = f"{start_year}_{end_year}Q{end_quarter}"
    return repo_root / "PANEL" / "DATA" / f"{cfg.country}_{tag}_{cfg.survey}_{cfg.harm_tag}_FULLSAMPLE.dta"


def fullsample_latest_alias_path(repo_root: Path, cfg: ENOEVersionConfig) -> Path:
    return repo_root / "PANEL" / "DATA" / f"{cfg.country}_{cfg.survey}_{cfg.harm_tag}_FULLSAMPLE_latest.dta"


def panel_output_path(repo_root: Path, cfg: ENOEVersionConfig, start_year: int, end_year: int, end_quarter: int) -> Path:
    tag = f"{start_year}_{end_year}Q{end_quarter}"
    return repo_root / "PANEL" / "DATA" / f"{cfg.country}_{tag}_PANEL_QUARTER.dta"


def panel_latest_alias_path(repo_root: Path, cfg: ENOEVersionConfig) -> Path:
    return repo_root / "PANEL" / "DATA" / f"{cfg.country}_PANEL_QUARTER_latest.dta"


def _version_num(token: str) -> int:
    match = re.search(r"V(\d+)", token)
    return int(match.group(1)) if match else -1


def _existing_dir_candidates(qroot: Path, pattern: re.Pattern[str]) -> list[tuple[tuple[int, ...], Path]]:
    out: list[tuple[tuple[int, ...], Path]] = []
    if not qroot.exists():
        return out
    for child in qroot.iterdir():
        if not child.is_dir():
            continue
        match = pattern.match(child.name)
        if not match:
            continue
        key = tuple(_version_num(group) for group in match.groups())
        out.append((key, child))
    out.sort(key=lambda item: item[0])
    return out


def resolve_existing_master_dir(qroot: Path, cfg: ENOEVersionConfig, year: int) -> Path | None:
    pattern = re.compile(rf"^{cfg.country}_{year}_{cfg.survey}_(V\d{{2}})_M$")
    candidates = _existing_dir_candidates(qroot, pattern)
    return candidates[-1][1] if candidates else None


def resolve_existing_harm_dir(qroot: Path, cfg: ENOEVersionConfig, year: int) -> Path | None:
    pattern = re.compile(
        rf"^{cfg.country}_{year}_{cfg.survey}_(V\d{{2}})_M_(V\d{{2}})_A_{cfg.harmonization_acronym}$"
    )
    candidates = _existing_dir_candidates(qroot, pattern)
    return candidates[-1][1] if candidates else None
