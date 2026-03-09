#!/usr/bin/env python3
"""
# Sample Size Audit

Audit HH/IND sample sizes for ENOE GLD do-files.

This script reads the raw ENOE SDEMT Stata files for each quarter and:
- counts IND as the number of person records after filtering
  `r_def == 0` and `c_res in {1,3}`;
- counts HH as the number of distinct household IDs (`folioh`) built
  from raw SDEMT components (with year-specific variants handled).

It then writes a CSV report with the current sample sizes found in
each `.do` file and the recomputed counts. With `--update`, it replaces
the values in the `<_Sample size (HH)_>` and `<_Sample size (IND)_>` tags.

## Usage

```bash
python Do-files/sample_size_audit/sample_size_audit.py
python Do-files/sample_size_audit/sample_size_audit.py --update
python Do-files/sample_size_audit/sample_size_audit.py --report sample_size_audit.csv
```

## Performance Notes

Parallel setup is implemented in `01_ENOE_Harmonization.do`.
- Parallel run time: 12 minutes 58 seconds.
- Parallelization: 21 batch files (one per year).
- Hardware: 56-core Mac with 192 GB RAM.
- Sequential run time: approximately 2 hours 20 minutes.
"""
import argparse
from pathlib import Path
import re
import sys

import pandas as pd
from pandas.api.types import is_string_dtype

QUARTERLY_AGENT_DIR = Path(__file__).resolve().parents[1] / "quarterly_agent"
if str(QUARTERLY_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(QUARTERLY_AGENT_DIR))

from versioning import load_version_config


def find_file(stata_dir: Path, token: str, suffix: str) -> Path | None:
    if not stata_dir.exists():
        return None
    candidates = [
        f"{token.upper()}{suffix}.dta",
        f"{token.lower()}{suffix}.dta",
        f"enoe_{token.lower()}{suffix}.dta",
        f"enoen_{token.lower()}{suffix}.dta",
    ]
    for name in candidates:
        path = stata_dir / name
        if path.exists():
            return path
    for path in stata_dir.glob(f"*{suffix}*.dta"):
        if token.lower() in path.name.lower():
            return path
    return None


def norm_series(series: pd.Series, width: int | None = None) -> pd.Series:
    if is_string_dtype(series):
        values = series.astype(str)
    else:
        values = pd.to_numeric(series, errors="coerce").astype("Int64").astype(str)
    values = values.replace("<NA>", "")
    if width:
        values = values.str.zfill(width)
    return values


def pick_col(columns_lower: list[str], col_map: dict[str, str], primary: str, alternates: list[str]) -> str | None:
    for name in [primary] + alternates:
        if name in columns_lower:
            return col_map[name]
    return None


def count_from_sdemt(path: Path, chunksize: int = 500000) -> tuple[int, int]:
    first = next(pd.read_stata(path, chunksize=1, convert_categoricals=False))
    columns_lower = [c.lower() for c in first.columns]
    col_map = {c.lower(): c for c in first.columns}

    cd_a = pick_col(columns_lower, col_map, "cd_a", [])
    ent = pick_col(columns_lower, col_map, "ent", ["cve_ent"])
    con = pick_col(columns_lower, col_map, "con", ["cve_mun"])
    v_sel = pick_col(columns_lower, col_map, "v_sel", [])
    n_hog = pick_col(columns_lower, col_map, "n_hog", [])
    h_mud = pick_col(columns_lower, col_map, "h_mud", [])

    if not all([cd_a, ent, con, v_sel, n_hog, h_mud]):
        missing = [
            name
            for name, val in [
                ("cd_a", cd_a),
                ("ent", ent),
                ("con", con),
                ("v_sel", v_sel),
                ("n_hog", n_hog),
                ("h_mud", h_mud),
            ]
            if val is None
        ]
        raise ValueError(f"missing columns {missing} in {path}")

    optional = ["tipo", "mes_cal", "ca", "n_ren", "r_def", "c_res"]
    cols_to_read = [cd_a, ent, con, v_sel, n_hog, h_mud]
    cols_to_read += [col_map[c] for c in columns_lower if c in optional]
    cols_to_read = list(dict.fromkeys(cols_to_read))

    hh_set: set[str] = set()
    ind_count = 0

    for chunk in pd.read_stata(path, columns=cols_to_read, chunksize=chunksize, convert_categoricals=False):
        chunk.columns = [c.lower() for c in chunk.columns]
        if "r_def" in chunk.columns and "c_res" in chunk.columns:
            r_def = pd.to_numeric(chunk["r_def"], errors="coerce")
            c_res = pd.to_numeric(chunk["c_res"], errors="coerce")
            chunk = chunk[(r_def == 0) & (c_res.isin([1, 3]))]
        if chunk.empty:
            continue
        ind_count += len(chunk)

        parts: list[pd.Series] = []
        parts.append(norm_series(chunk[cd_a.lower()], 2))
        parts.append(norm_series(chunk[ent.lower()], 2))
        parts.append(norm_series(chunk[con.lower()], 4))
        parts.append(norm_series(chunk[v_sel.lower()], 2))

        if "tipo" in chunk.columns and "mes_cal" in chunk.columns:
            parts.append(norm_series(chunk["tipo"]))
            parts.append(norm_series(chunk["mes_cal"]))
            if "ca" in chunk.columns:
                parts.append(norm_series(chunk["ca"]))

        parts.append(norm_series(chunk["n_hog"]))
        parts.append(norm_series(chunk["h_mud"]))

        folioh = parts[0]
        for part in parts[1:]:
            folioh = folioh.str.cat(part, na_rep="")
        hh_set.update(folioh.tolist())

    return len(hh_set), ind_count


def main() -> int:
    """
    Run the audit and optionally update the do-files.

    The script infers the year/quarter from the do-file path, then locates
    the corresponding raw SDEMT file under Data/Stata using common name
    patterns (e.g., SDEMT105.dta, enoe_sdemt105.dta, enoen_sdemt105.dta).
    """
    parser = argparse.ArgumentParser(description="Audit HH/IND sample sizes from raw ENOE SDEMT data.")
    parser.add_argument("--root", default=None, help="Repo root (defaults to script parent).")
    parser.add_argument("--report", default=None, help="CSV report path.")
    parser.add_argument("--update", action="store_true", help="Update sample size tags in .do files.")
    args = parser.parse_args()

    repo_root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]
    report_path = Path(args.report).resolve() if args.report else repo_root / "Do-files" / "sample_size_audit" / "sample_size_audit.csv"
    cfg = load_version_config(repo_root)

    files = sorted(repo_root.rglob(f"{cfg.country}_*_{cfg.survey}_V*_M_V*_A_{cfg.harmonization_acronym}_ALL.do"))
    path_q_re = re.compile(rf"{cfg.country}_(\d{{4}})_{cfg.survey}-(Q[1-4])")
    path_master_re = re.compile(rf"{cfg.country}_(\d{{4}})_{cfg.survey}_(V\d{{2}})_M$")

    hh_re = re.compile(r"(<_Sample size \(HH\)_>\s*\[)([^\]]+)(\]\s*</_Sample size \(HH\)_>)")
    ind_re = re.compile(r"(<_Sample size \(IND\)_>\s*\[)([^\]]+)(\]\s*</_Sample size \(IND\)_>)")

    rows = []
    updated = 0
    missing = 0

    for idx, do_file in enumerate(files, 1):
        m = path_q_re.search(str(do_file))
        if not m:
            continue
        year = int(m.group(1))
        quarter = m.group(2)
        qnum = int(quarter[1])
        suffix = f"{qnum}{str(year)[2:]}"

        master_candidates = []
        for child in do_file.parents[2].iterdir():
            if child.is_dir() and path_master_re.match(child.name):
                master_candidates.append(child)
        master_dir = sorted(master_candidates)[-1] if master_candidates else None
        if master_dir is None:
            missing += 1
            continue

        stata_dir = master_dir / "Data" / "Stata"
        sdemt = find_file(stata_dir, "sdemt", suffix)
        if sdemt is None:
            missing += 1
            continue

        hh, ind = count_from_sdemt(sdemt)

        text = do_file.read_text()
        hh_m = hh_re.search(text)
        ind_m = ind_re.search(text)
        cur_hh = None
        cur_ind = None
        if hh_m:
            cur_hh = int(hh_m.group(2).strip().replace(",", ""))
        if ind_m:
            cur_ind = int(ind_m.group(2).strip().replace(",", ""))

        match = cur_hh == hh and cur_ind == ind

        rows.append({
            "do_file": str(do_file),
            "year": str(year),
            "quarter": quarter,
            "current_hh": cur_hh,
            "current_ind": cur_ind,
            "computed_hh": hh,
            "computed_ind": ind,
            "match": "yes" if match else "no",
        })

        if args.update and not match:
            hh_fmt = f"{hh:,}"
            ind_fmt = f"{ind:,}"
            new_text = hh_re.sub(lambda m: f"{m.group(1)}{hh_fmt}{m.group(3)}", text)
            new_text = ind_re.sub(lambda m: f"{m.group(1)}{ind_fmt}{m.group(3)}", new_text)
            if new_text != text:
                do_file.write_text(new_text)
                updated += 1

        if idx % 10 == 0:
            print(f"processed {idx}/{len(files)}")

    report_path.write_text(
        "do_file,year,quarter,current_hh,current_ind,computed_hh,computed_ind,match\n"
        + "\n".join(
            f"{r['do_file']},{r['year']},{r['quarter']},{r['current_hh']},{r['current_ind']},{r['computed_hh']},{r['computed_ind']},{r['match']}"
            for r in rows
        )
        + "\n"
    )

    print(f"report: {report_path}")
    if args.update:
        print(f"updated: {updated}")
    if missing:
        print(f"missing SDEMT files: {missing}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
