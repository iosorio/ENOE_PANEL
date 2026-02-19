#!/usr/bin/env python3
"""Phase 1: detect and download ENOE quarterly microdata from INEGI.

Workflow:
1) Discover ENOE quarter records via INEGI Descarga Masiva API.
2) Compare remote records against a local state snapshot.
3) Download missing/updated quarter ZIP files into each quarter's
   Data/Original folder, validating ZIP signature.
4) Persist a state file for future incremental runs.
"""

from __future__ import annotations

import argparse
import base64
import datetime as dt
import hashlib
import json
import posixpath
import re
import shutil
import sys
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

BASE_URL = "https://www.inegi.org.mx"
API_BASE = f"{BASE_URL}/app/api/descarga/descarga/descargamasiva/lista"
USER_AGENT = "ENOE-Quarterly-Agent/1.0 (+phase1)"

PROGRAM_BASE_TITLES = [
    "Programas|Encuesta Nacional de Ocupación y Empleo (ENOE), población de 15 años y más de edad|",
    "Programas|Encuesta Nacional de Ocupación y Empleo (ENOE), población de 14 años y más de edad|",
]

ROMAN_TO_QUARTER = {"I": 1, "II": 2, "III": 3, "IV": 4}


@dataclass
class RemoteRecord:
    key: str
    year: int
    quarter: int
    variant: str
    source_id: str
    title: str
    path_logico: str
    url: str
    format_name: str
    size_label: str


def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def b64(text: str) -> str:
    return base64.b64encode(text.encode("utf-8")).decode("ascii")


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json_file(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def request_json(url: str, timeout: int, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    data = None
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, method=method.upper(), data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    return json.loads(raw)


def parse_quarter_from_title(title: str) -> int | None:
    match = re.search(r"\|\s*([IVX]+)\s+Trimestre", title, flags=re.IGNORECASE)
    if not match:
        return None
    roman = match.group(1).upper()
    return ROMAN_TO_QUARTER.get(roman)


def parse_variant_from_title(title: str) -> str:
    match = re.search(r"\(([^)]+)\)", title)
    if not match:
        return "UNKNOWN"
    return match.group(1).strip().upper()


def normalize_path_logico(path_logico: str) -> str:
    cleaned = path_logico.strip()
    if not cleaned.startswith("/"):
        cleaned = f"/{cleaned}"
    return posixpath.normpath(cleaned)


def parse_format_map(formats_raw: str, ext_raw: str) -> dict[str, tuple[str, str]]:
    formats = [f.strip().lower() for f in formats_raw.split("|") if f.strip()]
    ext_items = [e for e in ext_raw.split("|") if e.strip()]

    out: dict[str, tuple[str, str]] = {}
    for idx, fmt in enumerate(formats):
        if idx >= len(ext_items):
            continue
        parts = ext_items[idx].split("&")
        suffix = parts[0].strip() if parts else ""
        size = parts[1].strip() if len(parts) > 1 else ""
        if suffix:
            out[fmt] = (suffix, size)
    return out


def build_download_url(path_logico: str, suffix: str) -> str:
    normalized = normalize_path_logico(path_logico)
    quoted_path = "/" + "/".join(urllib.parse.quote(seg) for seg in normalized.split("/") if seg)
    return urllib.parse.urljoin(BASE_URL, f"/contenidos{quoted_path}{suffix}")


def variant_priority(variant: str) -> int:
    if variant == "ENOE":
        return 3
    if variant == "ENOEN":
        return 2
    return 1


def discover_remote_records(years: list[int], data_format: str, timeout: int, verbose: bool) -> dict[str, RemoteRecord]:
    records: dict[str, RemoteRecord] = {}

    for year in years:
        for program_title in PROGRAM_BASE_TITLES:
            payload = {
                "tinfo": "4",
                "ag": "0",
                "prog": "0",
                "cc": "0",
                "subtema": "0",
                "anio": str(year),
                "formato": "0",
                "datosAbiertos": "3",
                "titulo": b64(program_title + "Base de datos|"),
                "textoBuscar": "",
                "ingles": "0",
                "tipoInfo": "PROGRAMAS",
            }
            url = f"{API_BASE}/obtenerarchivos"
            try:
                rows = request_json(url=url, method="POST", payload=payload, timeout=timeout)
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                if verbose:
                    print(f"WARN year={year} title={program_title[:40]}...: {exc}", file=sys.stderr)
                continue

            if not isinstance(rows, list):
                continue

            for row in rows:
                title = str(row.get("titulo", ""))
                q = parse_quarter_from_title(title)
                if q is None:
                    continue

                fmt_map = parse_format_map(
                    formats_raw=str(row.get("formatos", "")),
                    ext_raw=str(row.get("extensiones", "")),
                )
                if data_format not in fmt_map:
                    continue

                suffix, size_label = fmt_map[data_format]
                path_logico = str(row.get("pathLogico", "")).strip()
                if not path_logico:
                    continue

                variant = parse_variant_from_title(title)
                url_download = build_download_url(path_logico=path_logico, suffix=suffix)
                key = f"{year}-Q{q}-{data_format}"

                candidate = RemoteRecord(
                    key=key,
                    year=year,
                    quarter=q,
                    variant=variant,
                    source_id=str(row.get("idTitulo", "")),
                    title=title,
                    path_logico=path_logico,
                    url=url_download,
                    format_name=data_format,
                    size_label=size_label,
                )

                existing = records.get(key)
                if existing is None:
                    records[key] = candidate
                else:
                    replace = False
                    if variant_priority(candidate.variant) > variant_priority(existing.variant):
                        replace = True
                    elif variant_priority(candidate.variant) == variant_priority(existing.variant):
                        replace = candidate.source_id > existing.source_id
                    if replace:
                        records[key] = candidate

    return dict(sorted(records.items(), key=lambda kv: (kv[1].year, kv[1].quarter, kv[0])))


def expected_zip_name(year: int, quarter: int) -> str:
    return f"original_MEX_{year}_ENOE-Q{quarter}.zip"


def legacy_zip_name(year: int, quarter: int) -> str:
    return f"original_MEX_{year}-Q{quarter}.zip"


def target_original_dir(repo_root: Path, year: int, quarter: int) -> Path:
    return (
        repo_root
        / f"MEX_{year}_ENOE-Q{quarter}"
        / f"MEX_{year}_ENOE_V01_M"
        / "Data"
        / "Original"
    )


def choose_zip_path(dest_dir: Path, year: int, quarter: int) -> Path:
    """Prefer existing file names to avoid duplicate downloads.

    Some quarters in this repo use a legacy naming pattern without `_ENOE`.
    """
    canonical = dest_dir / expected_zip_name(year, quarter)
    legacy = dest_dir / legacy_zip_name(year, quarter)
    if canonical.exists():
        return canonical
    if legacy.exists():
        return legacy
    return canonical


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_zip(url: str, dest: Path, timeout: int, overwrite: bool) -> dict[str, Any]:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and not overwrite:
        return {
            "status": "skipped_exists",
            "path": str(dest),
        }

    backup_path: Path | None = None
    if dest.exists() and overwrite:
        ts = dt.datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = dest.with_name(f"{dest.name}.bak-{ts}")
        shutil.move(str(dest), str(backup_path))

    part = dest.with_name(f"{dest.name}.part")
    if part.exists():
        part.unlink()

    req = urllib.request.Request(
        url=url,
        method="GET",
        headers={"User-Agent": USER_AGENT, "Accept": "*/*"},
    )

    bytes_written = 0
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp, part.open("wb") as out:
            while True:
                chunk = resp.read(1024 * 1024)
                if not chunk:
                    break
                out.write(chunk)
                bytes_written += len(chunk)
    except Exception:
        if part.exists():
            part.unlink()
        if backup_path is not None and not dest.exists():
            shutil.move(str(backup_path), str(dest))
        raise

    with part.open("rb") as fh:
        sig = fh.read(4)

    if sig != b"PK\x03\x04":
        head = part.read_bytes()[:120]
        part.unlink(missing_ok=True)
        if backup_path is not None and not dest.exists():
            shutil.move(str(backup_path), str(dest))
        return {
            "status": "failed_non_zip",
            "signature_hex": sig.hex(),
            "head_preview": head.decode("utf-8", errors="replace"),
        }

    if not zipfile.is_zipfile(part):
        part.unlink(missing_ok=True)
        if backup_path is not None and not dest.exists():
            shutil.move(str(backup_path), str(dest))
        return {
            "status": "failed_invalid_zip",
            "signature_hex": sig.hex(),
        }

    shutil.move(str(part), str(dest))

    return {
        "status": "downloaded",
        "path": str(dest),
        "bytes": bytes_written,
        "sha256": sha256_file(dest),
        "backup_path": str(backup_path) if backup_path else "",
    }


def parse_years(arg_years: str | None, start_year: int, end_year: int) -> list[int]:
    if arg_years:
        years: list[int] = []
        for token in arg_years.split(","):
            token = token.strip()
            if not token:
                continue
            years.append(int(token))
        return sorted(set(years))
    return list(range(start_year, end_year + 1))


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 1 ENOE INEGI detection + download")
    parser.add_argument("--repo-root", default=None, help="ENOE_PANEL root directory (defaults to script's repo root)")
    parser.add_argument("--state-file", default=None, help="Path to JSON state file")
    parser.add_argument("--format", default="dta", choices=["dta", "csv", "dbf", "sav"], help="Remote file format")
    parser.add_argument("--start-year", type=int, default=2005)
    parser.add_argument("--end-year", type=int, default=dt.datetime.now().year)
    parser.add_argument("--years", default=None, help="Comma-separated years override, e.g. 2024,2025")
    parser.add_argument("--timeout", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true", help="Detect only; do not download")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite local file when remote changed")
    parser.add_argument("--verbose", action="store_true")
    return parser


def main() -> int:
    args = build_arg_parser().parse_args()

    script_path = Path(__file__).resolve()
    default_repo_root = script_path.parents[2]
    repo_root = Path(args.repo_root).resolve() if args.repo_root else default_repo_root

    default_state = repo_root / "Do-files" / "quarterly_agent" / "state" / "inegi_enoe_phase1_state.json"
    state_path = Path(args.state_file).resolve() if args.state_file else default_state

    years = parse_years(args.years, args.start_year, args.end_year)
    if not years:
        print("No years requested.", file=sys.stderr)
        return 1

    state = read_json_file(state_path)
    prev_remote = state.get("remote_records", {}) if isinstance(state.get("remote_records", {}), dict) else {}

    remote_records = discover_remote_records(
        years=years,
        data_format=args.format,
        timeout=args.timeout,
        verbose=args.verbose,
    )

    downloads: dict[str, Any] = {}
    actions: list[dict[str, Any]] = []

    for key, rec in remote_records.items():
        dest_dir = target_original_dir(repo_root=repo_root, year=rec.year, quarter=rec.quarter)
        dest_file = choose_zip_path(dest_dir=dest_dir, year=rec.year, quarter=rec.quarter)
        local_exists = dest_file.exists()

        prev = prev_remote.get(key, {}) if isinstance(prev_remote.get(key, {}), dict) else {}
        remote_changed = bool(prev) and (
            prev.get("url") != rec.url or prev.get("source_id") != rec.source_id
        )

        action = {
            "key": key,
            "year": rec.year,
            "quarter": rec.quarter,
            "variant": rec.variant,
            "source_id": rec.source_id,
            "url": rec.url,
            "dest": str(dest_file),
            "local_exists": local_exists,
            "remote_changed": remote_changed,
            "status": "",
        }

        if args.dry_run:
            if not local_exists:
                action["status"] = "would_download_missing"
            elif remote_changed:
                action["status"] = "would_download_changed"
            else:
                action["status"] = "already_present"
            actions.append(action)
            continue

        if not local_exists:
            result = download_zip(url=rec.url, dest=dest_file, timeout=args.timeout, overwrite=args.overwrite)
            action["status"] = result.get("status", "")
            action["download"] = result
        elif remote_changed:
            result = download_zip(url=rec.url, dest=dest_file, timeout=args.timeout, overwrite=args.overwrite)
            action["status"] = result.get("status", "")
            action["download"] = result
        else:
            action["status"] = "already_present"
            action["download"] = {
                "status": "already_present",
                "path": str(dest_file),
                "sha256": sha256_file(dest_file),
            }

        downloads[key] = action.get("download", {})
        actions.append(action)

    remote_state: dict[str, Any] = {}
    for key, rec in remote_records.items():
        remote_state[key] = {
            "year": rec.year,
            "quarter": rec.quarter,
            "variant": rec.variant,
            "source_id": rec.source_id,
            "title": rec.title,
            "url": rec.url,
            "path_logico": rec.path_logico,
            "format": rec.format_name,
            "size_label": rec.size_label,
        }

    downloads_state = downloads
    if args.dry_run and isinstance(state.get("downloads"), dict):
        downloads_state = state.get("downloads", {})

    new_state = {
        "version": 1,
        "last_run_utc": utc_now_iso(),
        "config": {
            "format": args.format,
            "years": years,
            "dry_run": args.dry_run,
        },
        "remote_records": remote_state,
        "downloads": downloads_state,
    }

    write_json_file(state_path, new_state)

    total = len(actions)
    would_or_done = [a for a in actions if "download" in a.get("status", "") or a.get("status", "").startswith("would_download")]
    failed = [a for a in actions if a.get("status", "").startswith("failed_")]

    print(f"Phase 1 run complete. records={total} state={state_path}")
    print(f"downloads_or_would_download={len(would_or_done)} failures={len(failed)}")

    for item in actions:
        print(
            f"[{item['status']}] {item['year']}-Q{item['quarter']} {item['variant']} "
            f"id={item['source_id']} -> {item['dest']}"
        )

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
