#!/usr/bin/env python
"""Python quality-check runner inspired by World Bank qcheck.

This tool provides three report types:
- static: rule-based harmonization consistency checks.
- basic: per-variable descriptive statistics.
- categoric: category shares for low-cardinality variables.

It is designed to run on ENOE harmonized .dta files, while remaining
configurable through CLI options and optional custom JSON rules.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from pandas.api.types import is_numeric_dtype

QUARTERLY_AGENT_DIR = Path(__file__).resolve().parents[1] / "quarterly_agent"
if str(QUARTERLY_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(QUARTERLY_AGENT_DIR))

from versioning import harm_output_path, load_version_config, quarter_root, resolve_existing_harm_dir


VALID_VERSION_VALUES = {
    "isco_1968",
    "isco_1988",
    "isco_2008",
    "isic_2",
    "isic_3",
    "isic_3.1",
    "isic_4",
    "isced_1976",
    "isced_1997",
    "isced_2011",
}


@dataclass
class CheckResult:
    survey_id: str
    module: str
    check_id: str
    variable: str
    description: str
    severity: int
    failed_n: float | int | None
    failed_ratio: float | None


def parse_args() -> argparse.Namespace:
    script = Path(__file__).resolve()
    default_repo_root = script.parents[2]

    ap = argparse.ArgumentParser(description="Run qcheck-style quality checks on ENOE harmonized .dta files")
    ap.add_argument("--repo-root", default=str(default_repo_root), help="ENOE_PANEL root")
    ap.add_argument("--dataset", default=None, help="Single harmonized .dta path")
    ap.add_argument("--batch", action="store_true", help="Run over all available years/quarters")
    ap.add_argument("--start-year", type=int, default=2005)
    ap.add_argument("--end-year", type=int, default=2025)
    ap.add_argument("--quarters", default="1,2,3,4", help="Comma-separated list like 1,2,3,4")
    ap.add_argument("--include-2020q2", action="store_true", help="Include 2020-Q2 if present")

    ap.add_argument(
        "--reports",
        default="static,basic,categoric",
        help="Comma-separated subset of: static,basic,categoric",
    )
    ap.add_argument("--profile", choices=["core", "full"], default="full", help="Static check coverage")

    ap.add_argument("--weight-var", default="weight", help="Weight variable used for weighted basic/categoric")
    ap.add_argument("--categoric-vars", default=None, help="Comma-separated vars for categoric report")
    ap.add_argument("--max-categories", type=int, default=50)

    ap.add_argument(
        "--varlists-do",
        default=str(default_repo_root / "Do-files" / "Quality_Checks" / "helpers" / "Helper_GLD_VarLists.do"),
        help="Path to Helper_GLD_VarLists.do",
    )
    ap.add_argument(
        "--isic-codes",
        default=str(default_repo_root / "Do-files" / "Quality_Checks" / "helpers" / "isic_codes.txt"),
    )
    ap.add_argument(
        "--isco-codes",
        default=str(default_repo_root / "Do-files" / "Quality_Checks" / "helpers" / "isco_codes.txt"),
    )
    ap.add_argument(
        "--custom-rules",
        default=None,
        help="Optional JSON file with additional expression checks",
    )

    ap.add_argument(
        "--out-root",
        default=str(default_repo_root / "Output" / "Quality_Checks_Py"),
        help="Output root for report files",
    )
    ap.add_argument("--xlsx", action="store_true", help="Also write an Excel workbook per dataset")
    ap.add_argument("--strict", action="store_true", help="Exit non-zero if any dataset run fails")
    return ap.parse_args()


def split_csv(raw: str) -> list[str]:
    return [x.strip() for x in raw.split(",") if x.strip()]


def parse_quarters(raw: str) -> list[int]:
    quarters = sorted({int(x) for x in split_csv(raw)})
    for q in quarters:
        if q not in (1, 2, 3, 4):
            raise ValueError(f"Invalid quarter: {q}")
    return quarters


def parse_stata_tokens(raw: str) -> list[str]:
    text = raw.strip()
    if text.startswith("="):
        text = text[1:].strip()
    text = text.replace('""', '"')

    tokens: list[str] = []
    for m in re.finditer(r'"([^"]+)"|(\S+)', text):
        token = (m.group(1) or m.group(2) or "").strip()
        if token:
            tokens.append(token)
    return tokens


def load_varlists(path: Path) -> dict[str, list[str]]:
    globals_map: dict[str, list[str]] = {}
    global_re = re.compile(r"^\s*global\s+([A-Za-z0-9_]+)\s+(.+?)\s*$")

    for raw_line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("*"):
            continue
        m = global_re.match(line)
        if not m:
            continue
        name = m.group(1).strip().lower()
        value = m.group(2).strip()
        tokens = [tok.lower() for tok in parse_stata_tokens(value)]
        globals_map[name] = tokens

    return globals_map


def parse_pairs(group_tokens: Iterable[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for token in group_tokens:
        words = [w for w in token.split() if w]
        if len(words) >= 2:
            pairs.append((words[0], words[1]))
    return pairs


def parse_triples(group_tokens: Iterable[str]) -> list[tuple[str, str, str]]:
    triples: list[tuple[str, str, str]] = []
    for token in group_tokens:
        words = [w for w in token.split() if w]
        if len(words) >= 3:
            triples.append((words[0], words[1], words[2]))
    return triples


def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip().lower() for c in out.columns]
    return out


def numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def as_clean_string(series: pd.Series) -> pd.Series:
    out = series.astype("string").str.strip()
    out = out.fillna("")
    out = out.replace({"<na>": "", "nan": "", "none": ""})
    return out


def weighted_quantile(values: np.ndarray, weights: np.ndarray, quantiles: list[float]) -> np.ndarray:
    if values.size == 0 or weights.size == 0:
        return np.full(len(quantiles), np.nan)

    sorter = np.argsort(values)
    values_sorted = values[sorter]
    weights_sorted = weights[sorter]
    total_w = weights_sorted.sum()
    if total_w <= 0:
        return np.full(len(quantiles), np.nan)

    cum_w = np.cumsum(weights_sorted)
    # Equivalent to placing each mass at midpoint of its weight interval.
    probs = (cum_w - 0.5 * weights_sorted) / total_w
    return np.interp(quantiles, probs, values_sorted)


def add_result(
    rows: list[CheckResult],
    survey_id: str,
    module: str,
    check_id: str,
    variable: str,
    description: str,
    severity: int,
    failed_n: float | int | None,
    denominator: int | float | None = None,
    failed_ratio: float | None = None,
) -> None:
    ratio = failed_ratio
    if ratio is None and failed_n is not None and denominator not in (None, 0):
        ratio = float(failed_n) / float(denominator)

    rows.append(
        CheckResult(
            survey_id=survey_id,
            module=module,
            check_id=check_id,
            variable=variable,
            description=description,
            severity=severity,
            failed_n=failed_n,
            failed_ratio=ratio,
        )
    )


def load_code_universe(path: Path) -> dict[str, set[str]]:
    if not path.exists():
        return {}
    try:
        df = pd.read_csv(path, encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, encoding="latin-1")
    cols = {c.lower(): c for c in df.columns}
    if "version" not in cols or "code" not in cols:
        return {}

    out: dict[str, set[str]] = {}
    for version, group in df.groupby(df[cols["version"]].astype("string").str.lower()):
        codes = set(group[cols["code"]].astype("string").str.strip())
        out[str(version)] = {c for c in codes if c and c.lower() != "<na>"}
    return out


def infer_categoric_vars(df: pd.DataFrame, weight_var: str, max_categories: int) -> list[str]:
    vars_out: list[str] = []
    for col in df.columns:
        if col == weight_var:
            continue
        uniq = df[col].nunique(dropna=True)
        if 1 < uniq <= max_categories:
            vars_out.append(col)
    return vars_out


def run_basic_report(df: pd.DataFrame, survey_id: str, weight_var: str | None) -> pd.DataFrame:
    quantiles = [0.01, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.95, 0.99]
    q_names = ["p01", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "p99"]

    has_weight = bool(weight_var and weight_var in df.columns)
    w_all = numeric(df[weight_var]) if has_weight else None

    rows: list[dict[str, Any]] = []

    for col in df.columns:
        if not is_numeric_dtype(df[col]):
            continue

        x = numeric(df[col])
        n_total = int(len(x))
        n_missing = int(x.isna().sum())
        n_non_missing = n_total - n_missing
        n_zero = int((x == 0).sum())

        base_metrics: dict[str, Any] = {
            "missing_share": n_missing / n_total if n_total else np.nan,
            "non_missing_n": n_non_missing,
            "zero_share": n_zero / n_total if n_total else np.nan,
        }

        x_non_missing = x.dropna()
        if not x_non_missing.empty:
            base_metrics.update(
                {
                    "mean": float(x_non_missing.mean()),
                    "sd": float(x_non_missing.std(ddof=1)),
                    "max": float(x_non_missing.max()),
                    "min": float(x_non_missing.min()),
                    "num": int(x_non_missing.shape[0]),
                    "skewness": float(x_non_missing.skew()),
                    "kurtosis": float(x_non_missing.kurt()),
                }
            )
            q_values = x_non_missing.quantile(quantiles)
            for qn, qv in zip(q_names, q_values, strict=True):
                base_metrics[qn] = float(qv)
        else:
            for metric in ["mean", "sd", "max", "min", "num", "skewness", "kurtosis", *q_names]:
                base_metrics[metric] = np.nan

        for metric, value in base_metrics.items():
            rows.append(
                {
                    "survey_id": survey_id,
                    "variable": col,
                    "metric": metric,
                    "value": value,
                    "weighted": "no",
                }
            )

        if has_weight:
            w = numeric(w_all)
            valid_w = w.notna() & (w > 0)
            if valid_w.any():
                # Shares over observations with valid positive weights.
                miss_w = np.average(x.isna()[valid_w].astype(float), weights=w[valid_w])
                zero_w = np.average((x.fillna(np.nan) == 0)[valid_w].astype(float), weights=w[valid_w])

                rows.append(
                    {
                        "survey_id": survey_id,
                        "variable": col,
                        "metric": "missing_share_w",
                        "value": float(miss_w),
                        "weighted": "yes",
                    }
                )
                rows.append(
                    {
                        "survey_id": survey_id,
                        "variable": col,
                        "metric": "zero_share_w",
                        "value": float(zero_w),
                        "weighted": "yes",
                    }
                )

                valid_xw = x.notna() & valid_w
                if valid_xw.any():
                    xv = x[valid_xw].to_numpy(dtype=float)
                    wv = w[valid_xw].to_numpy(dtype=float)

                    w_mean = float(np.average(xv, weights=wv))
                    w_var = float(np.average((xv - w_mean) ** 2, weights=wv))
                    w_sd = float(math.sqrt(w_var))
                    w_q = weighted_quantile(xv, wv, quantiles)

                    rows.append(
                        {
                            "survey_id": survey_id,
                            "variable": col,
                            "metric": "mean_w",
                            "value": w_mean,
                            "weighted": "yes",
                        }
                    )
                    rows.append(
                        {
                            "survey_id": survey_id,
                            "variable": col,
                            "metric": "sd_w",
                            "value": w_sd,
                            "weighted": "yes",
                        }
                    )
                    for qn, qv in zip(q_names, w_q, strict=True):
                        rows.append(
                            {
                                "survey_id": survey_id,
                                "variable": col,
                                "metric": f"{qn}_w",
                                "value": float(qv),
                                "weighted": "yes",
                            }
                        )

    if not rows:
        return pd.DataFrame(columns=["survey_id", "variable", "metric", "value", "weighted"])
    return pd.DataFrame(rows)


def run_categoric_report(
    df: pd.DataFrame,
    survey_id: str,
    weight_var: str | None,
    categoric_vars: list[str],
) -> pd.DataFrame:
    has_weight = bool(weight_var and weight_var in df.columns)
    w = numeric(df[weight_var]) if has_weight else None

    rows: list[dict[str, Any]] = []
    for var in categoric_vars:
        if var not in df.columns:
            continue

        cat = df[var].copy()
        cat = cat.astype("string").fillna("<MISSING>")

        if has_weight:
            w_valid = w.fillna(0)
            grouped = (
                pd.DataFrame({"cat": cat, "w": w_valid})
                .groupby("cat", dropna=False, sort=False, observed=False)["w"]
                .sum()
            )
            total = float(grouped.sum())
            for value, freq in grouped.items():
                share = float(freq / total) if total > 0 else np.nan
                rows.append(
                    {
                        "survey_id": survey_id,
                        "variable": var,
                        "category": str(value),
                        "frequency": float(freq),
                        "share": share,
                        "weighted": "yes",
                    }
                )
        else:
            grouped = cat.value_counts(dropna=False, sort=False)
            total = int(grouped.sum())
            for value, freq in grouped.items():
                share = float(freq / total) if total > 0 else np.nan
                rows.append(
                    {
                        "survey_id": survey_id,
                        "variable": var,
                        "category": str(value),
                        "frequency": int(freq),
                        "share": share,
                        "weighted": "no",
                    }
                )

    if not rows:
        return pd.DataFrame(columns=["survey_id", "variable", "category", "frequency", "share", "weighted"])

    out = pd.DataFrame(rows)
    out = out.sort_values(["variable", "category"], kind="stable").reset_index(drop=True)
    return out


def parse_cat_limits(name: str) -> tuple[int, int, int | None] | None:
    parts = name.split("_")
    if len(parts) == 3:
        try:
            return int(parts[1]), int(parts[2]), None
        except ValueError:
            return None
    if len(parts) == 4:
        try:
            return int(parts[1]), int(parts[2]), int(parts[3])
        except ValueError:
            return None
    return None


def run_custom_rules(
    df: pd.DataFrame,
    survey_id: str,
    custom_rules_path: Path,
    rows: list[CheckResult],
) -> None:
    payload = json.loads(custom_rules_path.read_text(encoding="utf-8"))
    checks = payload.get("checks", [])
    if not isinstance(checks, list):
        return

    for idx, rule in enumerate(checks, start=1):
        if not isinstance(rule, dict):
            continue

        check_id = str(rule.get("id", f"custom.rule_{idx}"))
        module = str(rule.get("module", "Custom"))
        variable = str(rule.get("variable", "*"))
        description = str(rule.get("description", "Custom expression check"))
        severity = int(rule.get("severity", 1))
        expr = rule.get("expr")
        where = rule.get("where")

        if not expr:
            add_result(
                rows,
                survey_id,
                module,
                check_id,
                variable,
                "Rule missing 'expr'",
                severity,
                failed_n=None,
                failed_ratio=np.nan,
            )
            continue

        try:
            base_mask = pd.Series(True, index=df.index)
            if where:
                where_mask = df.eval(str(where), engine="python")
                if not isinstance(where_mask, pd.Series):
                    where_mask = pd.Series(bool(where_mask), index=df.index)
                base_mask &= where_mask.fillna(False).astype(bool)

            fail_mask = df.eval(str(expr), engine="python")
            if not isinstance(fail_mask, pd.Series):
                fail_mask = pd.Series(bool(fail_mask), index=df.index)
            fail_mask = fail_mask.fillna(False).astype(bool)
            fail_mask &= base_mask

            failed_n = int(fail_mask.sum())
            if failed_n > 0:
                add_result(
                    rows,
                    survey_id,
                    module,
                    check_id,
                    variable,
                    description,
                    severity,
                    failed_n,
                    denominator=int(base_mask.sum()) if int(base_mask.sum()) > 0 else len(df),
                )
        except Exception as exc:  # noqa: BLE001
            add_result(
                rows,
                survey_id,
                module,
                check_id,
                variable,
                f"Custom rule evaluation error: {exc}",
                severity,
                failed_n=None,
                failed_ratio=np.nan,
            )


def run_static_report(
    df_in: pd.DataFrame,
    survey_id: str,
    dataset_path: Path,
    varlists: dict[str, list[str]],
    profile: str,
    isic_universe: dict[str, set[str]],
    isco_universe: dict[str, set[str]],
    custom_rules_path: Path | None,
) -> pd.DataFrame:
    rows: list[CheckResult] = []
    df = normalize_columns(df_in)
    n_obs = len(df)

    all_vars = varlists.get("all_vars", [])
    numeric_vars = varlists.get("numeric_vars", [])
    string_vars = varlists.get("string_vars", [])
    invariant_vars = varlists.get("invariant_vars", [])
    change_should_vars = varlists.get("change_should_vars", [])
    hh_level_vars = varlists.get("hh_level_vars", [])
    cat_list_names = varlists.get("cat_list_names", [])

    # 1.1 filename naming convention
    filename = dataset_path.name
    file_pat = re.compile(
        r"^[A-Za-z]{3}_[0-9]{4}_[A-Za-z0-9-]+_[Vv][0-9]{2}_M_[Vv][0-9]{2}_A_[A-Za-z]{3}_[A-Za-z_]+\.dta$"
    )
    if not file_pat.match(filename):
        add_result(
            rows,
            survey_id,
            "Overall",
            "overall.filename_convention",
            "filename",
            "Filename being checked does not follow naming convention",
            1,
            failed_n=None,
            failed_ratio=np.nan,
        )

    # 1.2 variable from dictionary not in data
    for var in all_vars:
        if var not in df.columns:
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.variable_not_in_data",
                var,
                "Variable not in data",
                1,
                failed_n=None,
                failed_ratio=np.nan,
            )

    # 1.3 variable in data not in dictionary
    all_vars_set = set(all_vars)
    for var in df.columns:
        if var not in all_vars_set:
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.variable_not_in_dictionary",
                var,
                "Variable not in dictionary",
                1,
                failed_n=None,
                failed_ratio=np.nan,
            )

    # 1.4 variable has all missing
    for var in all_vars:
        if var in df.columns and df[var].isna().all():
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.all_values_missing",
                var,
                "All values missing",
                99,
                failed_n=n_obs,
                denominator=n_obs,
            )

    # 1.5 numeric vars are numeric
    for var in numeric_vars:
        if var in df.columns and not is_numeric_dtype(df[var]):
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.numeric_type_mismatch",
                var,
                "A numeric var is not numeric",
                1,
                failed_n=None,
                failed_ratio=np.nan,
            )

    # 1.6 string vars are string-like
    for var in string_vars:
        if var in df.columns and is_numeric_dtype(df[var]):
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.string_type_mismatch",
                var,
                "A string var is not string",
                1,
                failed_n=None,
                failed_ratio=np.nan,
            )

    # 1.7 invariant vars do not change
    for var in invariant_vars:
        if var in df.columns and df[var].nunique(dropna=False) > 1:
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.invariant_changes",
                var,
                "Invariant variable takes 2+ values",
                1,
                failed_n=None,
                failed_ratio=np.nan,
            )

    # 1.8 variables that should vary but don't
    for var in change_should_vars:
        if var in df.columns and df[var].nunique(dropna=True) == 1:
            add_result(
                rows,
                survey_id,
                "Overall",
                "overall.variable_unique_dataset",
                var,
                "Variable is unique in dataset",
                99,
                failed_n=None,
                failed_ratio=np.nan,
            )

    # 1.9 hh-level vars do not vary within household
    if "hhid" in df.columns:
        for var in hh_level_vars:
            if var not in df.columns:
                continue
            grp_nuniq = df.groupby("hhid", dropna=False)[var].nunique(dropna=False)
            bad_hh = set(grp_nuniq[grp_nuniq > 1].index)
            if bad_hh:
                failed_n = int(df["hhid"].isin(bad_hh).sum())
                add_result(
                    rows,
                    survey_id,
                    "Overall",
                    "overall.not_unique_within_hh",
                    var,
                    "Variable is not unique within HH",
                    99,
                    failed_n=failed_n,
                    denominator=n_obs,
                )

    # 1.10 categorical ranges
    for list_name in cat_list_names:
        limits = parse_cat_limits(list_name)
        if limits is None:
            continue
        low_lim, up_lim, extra = limits
        for var in varlists.get(list_name, []):
            if var not in df.columns:
                continue

            raw = df[var]
            num = numeric(raw)
            bad_cast = raw.notna() & num.isna()
            in_range = num.between(low_lim, up_lim, inclusive="both")
            if extra is not None:
                in_range = in_range | (num == extra)
            valid = raw.isna() | in_range
            invalid = (~valid) | bad_cast

            failed_n = int(invalid.sum())
            if failed_n > 0:
                descr = (
                    f"Variable values outside of range {low_lim}, {up_lim} (+ {extra})"
                    if extra is not None
                    else f"Variable values outside of range {low_lim}, {up_lim}"
                )
                add_result(
                    rows,
                    survey_id,
                    "Overall",
                    "overall.categorical_range",
                    var,
                    descr,
                    1,
                    failed_n=failed_n,
                    denominator=n_obs,
                )

    # 1.11 survey versions agree with filename
    m_versions = re.search(r"_([Vv][0-9]{2})_M_([Vv][0-9]{2})_A_", filename)
    if m_versions:
        file_vermast = m_versions.group(1).lower()
        file_veralt = m_versions.group(2).lower()

        if "vermast" in df.columns:
            bad = as_clean_string(df["vermast"]).str.lower().ne(file_vermast)
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Overall",
                    "overall.vermast_filename_mismatch",
                    "vermast",
                    "Version of Master per filename unequal to vermast",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )

        if "veralt" in df.columns:
            bad = as_clean_string(df["veralt"]).str.lower().ne(file_veralt)
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Overall",
                    "overall.veralt_filename_mismatch",
                    "veralt",
                    "Version of Alter per filename unequal to veralt",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )

    # 2.1 countrycode/vermast/veralt are str3
    for var in varlists.get("surv_str3", []):
        if var not in df.columns:
            continue
        length = as_clean_string(df[var]).str.len()
        bad = (length != 3) & (length > 0)
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Survey & ID",
                "surveyid.str3_length",
                var,
                f"{var} is not 3-character string",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 2.2 survname has only alnum or dash
    if "survname" in df.columns:
        survname = as_clean_string(df["survname"])
        bad = survname.ne("") & (~survname.str.match(r"^[A-Za-z0-9-]+$", na=False))
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Survey & ID",
                "surveyid.survname_format",
                "survname",
                "Survey name should only be alphanumeric or contain a dash",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 2.3 year in reasonable 4-digit range
    if "year" in df.columns:
        year = numeric(df["year"])
        bad = year.notna() & ((year < 1880) | (year > 2100))
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Survey & ID",
                "surveyid.year_range",
                "year",
                "Variable year is outside [1880, 2100]",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 2.4 pid unique across observations
    if "pid" in df.columns:
        ndistinct = int(df["pid"].nunique(dropna=False))
        if ndistinct != n_obs and n_obs > 0:
            ratio = ndistinct / n_obs
            add_result(
                rows,
                survey_id,
                "Survey & ID",
                "surveyid.pid_not_unique",
                "pid",
                "pid is not unique. Distinct to total ratio",
                1,
                failed_n=n_obs - ndistinct,
                failed_ratio=ratio,
            )

    # 2.5 international classification versions
    for var in varlists.get("int_class_versions", []):
        if var not in df.columns:
            continue
        values = as_clean_string(df[var]).str.lower()
        bad = values.ne("") & (~values.isin(VALID_VERSION_VALUES))
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Survey & ID",
                "surveyid.int_class_version_invalid",
                var,
                f"Variable {var} is not correctly defined",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 3.1 administrative hierarchy checks
    for adm1, adm2, adm3 in parse_triples(varlists.get("subnat_hierarchy", [])):
        if not all(v in df.columns for v in (adm1, adm2, adm3)):
            continue
        bad = (df[adm3].notna() & df[adm2].isna()) | (df[adm2].notna() & df[adm1].isna())
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Geography",
                "geography.admin_hierarchy",
                f"{adm1} {adm2} {adm3}",
                "Admin ID structure is not hierarchically consistent",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 4.1 hsize equals number of members per hhid
    if "hsize" in df.columns and "hhid" in df.columns:
        hh_sizes = df.groupby("hhid", dropna=False).size()
        obs_hh_size = df["hhid"].map(hh_sizes)
        hsize = numeric(df["hsize"])
        bad = hsize.notna() & (obs_hh_size != hsize)
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Demography",
                "demography.hsize_consistency",
                "hsize",
                "HH size differs from number of obs per HH",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 4.2 age validity
    if "age" in df.columns:
        age = numeric(df["age"])
        not_integer = age.notna() & (np.floor(age) != age)
        outside_range = age.notna() & ((age < 0) | (age > 120))
        bad = not_integer | outside_range
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Demography",
                "demography.age_validity",
                "age",
                "Age shows unexpected values",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 4.3 one head per household
    if "relationharm" in df.columns and "hhid" in df.columns:
        heads = int((numeric(df["relationharm"]) == 1).sum())
        n_hh = int(df["hhid"].nunique(dropna=False))
        if n_hh > 0 and heads != n_hh:
            add_result(
                rows,
                survey_id,
                "Demography",
                "demography.one_head_per_hh",
                "relationharm",
                "Ratio of heads to HHID is not 1",
                1,
                failed_n=abs(heads - n_hh),
                failed_ratio=heads / n_hh,
            )

    # 5.1 migration skip-pattern
    never_migrated = varlists.get("never_migrated", [])
    if "migrated_binary" in df.columns:
        mig = numeric(df["migrated_binary"])
        for var in never_migrated:
            if var not in df.columns:
                continue
            bad = (mig == 0) & df[var].notna()
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Migration",
                    "migration.answers_when_never_migrated",
                    var,
                    f"Variable {var} has answers although migrated_binary indicates never migrated",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )
    else:
        for var in never_migrated:
            if var in df.columns:
                add_result(
                    rows,
                    survey_id,
                    "Migration",
                    "migration.base_variable_missing",
                    var,
                    f"Variable {var} has migration answers although migrated_binary is missing",
                    1,
                    failed_n=None,
                    failed_ratio=np.nan,
                )

    # 6.1 educy consistency
    if "educy" in df.columns:
        educy = numeric(df["educy"])
        bad = educy.notna() & (educy < 0)
        if "age" in df.columns:
            age = numeric(df["age"])
            bad = bad | (educy.notna() & age.notna() & (educy > age))
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Education",
                "education.educy_validity",
                "educy",
                "Years in education show unexpected values",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 6.2-6.4 education hierarchy and concordance
    if all(v in df.columns for v in ("educat4", "educat5", "educat7")):
        e4 = numeric(df["educat4"])
        e5 = numeric(df["educat5"])
        e7 = numeric(df["educat7"])

        bad_hier = (e7.notna() & e5.isna()) | (e5.notna() & e4.isna())
        if bad_hier.any():
            add_result(
                rows,
                survey_id,
                "Education",
                "education.educat_hierarchy",
                "educat4 educat5 educat7",
                "Educat 4/5/7 hierarchy not respected",
                1,
                failed_n=int(bad_hier.sum()),
                denominator=n_obs,
            )

        map_7_to_5 = {1: 1, 2: 2, 3: 3, 4: 3, 5: 4, 6: 5, 7: 5}
        expected5 = e7.map(map_7_to_5)
        bad_75 = e7.notna() & e5.notna() & (expected5 != e5)
        if bad_75.any():
            add_result(
                rows,
                survey_id,
                "Education",
                "education.educat7_to_educat5",
                "educat7 educat5",
                "Educat 5 <-> 7 correspondence not holding",
                1,
                failed_n=int(bad_75.sum()),
                denominator=n_obs,
            )

        map_5_to_4 = {1: 1, 2: 2, 3: 2, 4: 3, 5: 4}
        expected4 = e5.map(map_5_to_4)
        bad_54 = e5.notna() & e4.notna() & (expected4 != e4)
        if bad_54.any():
            add_result(
                rows,
                survey_id,
                "Education",
                "education.educat5_to_educat4",
                "educat5 educat4",
                "Educat 4 <-> 5 correspondence not holding",
                1,
                failed_n=int(bad_54.sum()),
                denominator=n_obs,
            )

    if "educat_isced" in df.columns:
        eisced = numeric(df["educat_isced"])
        bad = eisced.notna() & ((eisced < 100) | (eisced > 999))
        if bad.any():
            add_result(
                rows,
                survey_id,
                "Education",
                "education.isced_format",
                "educat_isced",
                "ISCED code is not three digits",
                1,
                failed_n=int(bad.sum()),
                denominator=n_obs,
            )

    # 7.1 vocational skip-pattern
    never_trained = varlists.get("never_trained", [])
    if "vocational" in df.columns:
        vocational = numeric(df["vocational"])
        for var in never_trained:
            if var not in df.columns:
                continue
            bad = (vocational == 0) & df[var].notna()
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Training",
                    "training.answers_when_not_trained",
                    var,
                    f"Variable {var} has answers although vocational indicates no training",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )
    else:
        for var in never_trained:
            if var in df.columns:
                add_result(
                    rows,
                    survey_id,
                    "Training",
                    "training.base_variable_missing",
                    var,
                    f"Variable {var} has vocational answers although vocational is missing",
                    1,
                    failed_n=None,
                    failed_ratio=np.nan,
                )

    # Full-profile labour checks.
    if profile == "full":
        # 8.1/8.2 unemployed not-posed checks
        if "lstatus" in df.columns:
            lstatus = numeric(df["lstatus"])
            for var in varlists.get("not_posed_unemployed_week", []):
                if var in df.columns:
                    bad = (lstatus == 2) & df[var].notna()
                    if bad.any():
                        add_result(
                            rows,
                            survey_id,
                            "Labour",
                            "labour.unemployed_week_skip_pattern",
                            var,
                            f"Variable {var} has labour answers for 7-day unemployed",
                            1,
                            failed_n=int(bad.sum()),
                            denominator=n_obs,
                        )

        if "lstatus_year" in df.columns:
            lstatus_year = numeric(df["lstatus_year"])
            for var in varlists.get("not_posed_unemployed_year", []):
                if var in df.columns:
                    bad = (lstatus_year == 2) & df[var].notna()
                    if bad.any():
                        add_result(
                            rows,
                            survey_id,
                            "Labour",
                            "labour.unemployed_year_skip_pattern",
                            var,
                            f"Variable {var} has labour answers for 12-month unemployed",
                            1,
                            failed_n=int(bad.sum()),
                            denominator=n_obs,
                        )

        # 8.3/8.4 NLF reason completion checks
        if "lstatus" in df.columns and "nlfreason" in df.columns:
            lstatus = numeric(df["lstatus"])
            nlf_total = int((lstatus == 3).sum())
            nlf_missing = int(((lstatus == 3) & df["nlfreason"].isna()).sum())
            if 0 < nlf_missing < nlf_total:
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.nlfreason_partial_missing_week",
                    "nlfreason",
                    "Some NLF individuals answered nlfreason while others did not",
                    1,
                    failed_n=nlf_missing,
                    denominator=nlf_total,
                )

        if "lstatus_year" in df.columns and "nlfreason_year" in df.columns:
            lstatus_year = numeric(df["lstatus_year"])
            nlf_total = int((lstatus_year == 3).sum())
            nlf_missing = int(((lstatus_year == 3) & df["nlfreason_year"].isna()).sum())
            if 0 < nlf_missing < nlf_total:
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.nlfreason_partial_missing_year",
                    "nlfreason_year",
                    "Some 12-month NLF individuals answered nlfreason_year while others did not",
                    1,
                    failed_n=nlf_missing,
                    denominator=nlf_total,
                )

        # 8.5/8.6 NLF skip-pattern checks
        if "lstatus" in df.columns:
            lstatus = numeric(df["lstatus"])
            for var in varlists.get("not_posed_nlf_week", []):
                if var in df.columns:
                    bad = (lstatus == 3) & df[var].notna()
                    if bad.any():
                        add_result(
                            rows,
                            survey_id,
                            "Labour",
                            "labour.nlf_week_skip_pattern",
                            var,
                            f"Variable {var} has labour answers for 7-day NLF",
                            1,
                            failed_n=int(bad.sum()),
                            denominator=n_obs,
                        )

        if "lstatus_year" in df.columns:
            lstatus_year = numeric(df["lstatus_year"])
            for var in varlists.get("not_posed_nlf_year", []):
                if var in df.columns:
                    bad = (lstatus_year == 3) & df[var].notna()
                    if bad.any():
                        add_result(
                            rows,
                            survey_id,
                            "Labour",
                            "labour.nlf_year_skip_pattern",
                            var,
                            f"Variable {var} has labour answers for 12-month NLF",
                            1,
                            failed_n=int(bad.sum()),
                            denominator=n_obs,
                        )

        # 8.7 Industry 10 vs 4 correspondence
        for cat10, cat4 in parse_pairs(varlists.get("industry_cat_concordance", [])):
            if not all(v in df.columns for v in (cat10, cat4)):
                continue
            c10 = numeric(df[cat10])
            c4 = numeric(df[cat4])
            bad = (
                ((c10 == 1) & (c4 != 1))
                | ((c10 == 2) & (c4 != 2))
                | ((c10 == 3) & (c4 != 2))
                | ((c10 == 4) & (c4 != 2))
                | ((c10 == 5) & (c4 != 2))
                | ((c10 == 6) & (c4 != 3))
                | ((c10 == 7) & (c4 != 3))
                | ((c10 == 8) & (c4 != 3))
                | ((c10 == 9) & (c4 != 3))
                | ((c10 == 10) & (c4 != 4))
            )
            bad = bad & c10.notna() & c4.notna()
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.industrycat10_industrycat4_correspondence",
                    f"{cat10} {cat4}",
                    "10-category and 4-category industry variables do not correspond",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )

        # 8.8/8.9 Wage descending logic.
        def check_wage_desc(variables: list[str], check_id: str, description: str) -> None:
            present = [v for v in variables if v in df.columns]
            if len(present) < 2:
                return
            v1 = numeric(df[present[0]])
            v2 = numeric(df[present[1]])
            bad = v1.notna() & v2.notna() & (v1 < v2)
            if len(present) == 3:
                v3 = numeric(df[present[2]])
                bad = bad | (v2.notna() & v3.notna() & (v2 < v3))
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    check_id,
                    " ".join(variables),
                    description,
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )

        check_wage_desc(
            ["wage_total", "wage_total_2", "t_wage_others"],
            "labour.wage_desc_7day",
            "Total wage components do not follow primary >= secondary >= other (7-day)",
        )
        check_wage_desc(
            ["wage_total_year", "wage_total_2_year", "t_wage_others_year"],
            "labour.wage_desc_12month",
            "Total wage components do not follow primary >= secondary >= other (12-month)",
        )

        # 8.10-8.12 compensation consistency
        for a, b, cid, msg in [
            (
                "t_wage_nocompen_total",
                "t_wage_total",
                "labour.nocomp_gt_total_7day",
                "7-day total wage without compensation is larger than with compensation",
            ),
            (
                "t_wage_nocompen_total_year",
                "t_wage_total_year",
                "labour.nocomp_gt_total_12month",
                "12-month total wage without compensation is larger than with compensation",
            ),
            (
                "linc_nc",
                "laborincome",
                "labour.linc_nc_gt_laborincome",
                "Overall total wage without compensation is larger than with compensation",
            ),
        ]:
            if a in df.columns and b in df.columns:
                va = numeric(df[a])
                vb = numeric(df[b])
                bad = va.notna() & vb.notna() & (va > vb)
                if bad.any():
                    add_result(
                        rows,
                        survey_id,
                        "Labour",
                        cid,
                        f"{a} {b}",
                        msg,
                        1,
                        failed_n=int(bad.sum()),
                        denominator=n_obs,
                    )

        # 8.13/8.14 humanly impossible hours totals
        for x, y, cid in [
            ("whours", "whours_2", "labour.whours_total_7day"),
            ("whours_year", "whours_2_year", "labour.whours_total_12month"),
        ]:
            if x in df.columns and y in df.columns:
                vx = numeric(df[x])
                vy = numeric(df[y])
                total_h = vx.fillna(0) + vy.fillna(0)
                bad = total_h > 140
                if bad.any():
                    add_result(
                        rows,
                        survey_id,
                        "Labour",
                        cid,
                        f"{x} {y}",
                        "Combined weekly hours across jobs exceed 140",
                        1,
                        failed_n=int(bad.sum()),
                        denominator=n_obs,
                    )

        # 8.15/8.16 overall income must dominate component totals
        for overall, component, cid, msg in [
            (
                "linc_nc",
                "t_wage_nocompen_total",
                "labour.linc_nc_lt_component_7day",
                "linc_nc is smaller than 7-day non-comp wage total",
            ),
            (
                "linc_nc",
                "t_wage_nocompen_total_year",
                "labour.linc_nc_lt_component_12month",
                "linc_nc is smaller than 12-month non-comp wage total",
            ),
            (
                "laborincome",
                "t_wage_total",
                "labour.laborincome_lt_component_7day",
                "laborincome is smaller than 7-day wage total",
            ),
            (
                "laborincome",
                "t_wage_total_year",
                "labour.laborincome_lt_component_12month",
                "laborincome is smaller than 12-month wage total",
            ),
        ]:
            if overall in df.columns and component in df.columns:
                vo = numeric(df[overall])
                vc = numeric(df[component])
                bad = (vo.notna() & vc.notna() & (vo < vc)) | (vo.isna() & vc.notna())
                if bad.any():
                    add_result(
                        rows,
                        survey_id,
                        "Labour",
                        cid,
                        f"{overall} {component}",
                        msg,
                        1,
                        failed_n=int(bad.sum()),
                        denominator=n_obs,
                    )
            elif component in df.columns and overall not in df.columns:
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    f"{cid}.overall_missing",
                    f"{overall} {component}",
                    f"Variable {component} is in data but {overall} is missing",
                    1,
                    failed_n=None,
                    failed_ratio=np.nan,
                )

        # 8.17/8.18 isic/isco lengths
        for var in varlists.get("isic_check", []):
            if var not in df.columns:
                continue
            s = as_clean_string(df[var])
            length = s.str.len()
            bad = s.ne("") & (~length.isin([1, 4]))
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.isic_length",
                    var,
                    "ISIC code is not length 1 or 4",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )

        for var in varlists.get("isco_check", []):
            if var not in df.columns:
                continue
            s = as_clean_string(df[var])
            length = s.str.len()
            bad = s.ne("") & (length != 4)
            if bad.any():
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.isco_length",
                    var,
                    "ISCO code is not length 4",
                    1,
                    failed_n=int(bad.sum()),
                    denominator=n_obs,
                )

        # 8.19 industry_orig present while industrycat10 missing
        for orig, cat in parse_pairs(varlists.get("industry_alignment", [])):
            if orig in df.columns and cat in df.columns:
                bad = df[orig].notna() & df[cat].isna()
                if bad.any():
                    add_result(
                        rows,
                        survey_id,
                        "Labour",
                        "labour.industry_orig_missing_cat10",
                        f"{orig} {cat}",
                        "industry_orig not missing but industrycat10 is missing",
                        1,
                        failed_n=int(bad.sum()),
                        denominator=n_obs,
                    )

        # 8.20 lstatus missing for prime age
        for lvar in ["lstatus", "lstatus_year"]:
            if lvar in df.columns and "age" in df.columns:
                age = numeric(df["age"])
                lv = numeric(df[lvar])
                bad = lv.isna() & age.between(15, 65, inclusive="both")
                if bad.any():
                    add_result(
                        rows,
                        survey_id,
                        "Labour",
                        "labour.lstatus_missing_prime_age",
                        lvar,
                        f"{lvar} has missing values for ages 15-65",
                        1,
                        failed_n=int(bad.sum()),
                        denominator=n_obs,
                    )

        # 8.21/8.22 universe membership
        if "isic_version" in df.columns and isic_universe:
            version = as_clean_string(df["isic_version"]).str.lower()
            version_value = next((x for x in version if x), "")
            allowed_codes = isic_universe.get(version_value, set())
            if allowed_codes:
                for var in varlists.get("isic_check", []):
                    if var not in df.columns:
                        continue
                    codes = as_clean_string(df[var])
                    bad = codes.ne("") & (~codes.isin(allowed_codes))
                    if bad.any():
                        add_result(
                            rows,
                            survey_id,
                            "Labour",
                            "labour.isic_not_in_universe",
                            var,
                            f"{var} has ISIC codes not in ISIC universe",
                            1,
                            failed_n=int(bad.sum()),
                            denominator=n_obs,
                        )

        if "isco_version" in df.columns and isco_universe:
            version = as_clean_string(df["isco_version"]).str.lower()
            version_value = next((x for x in version if x), "")
            allowed_codes = isco_universe.get(version_value, set())
            if allowed_codes:
                for var in varlists.get("isco_check", []):
                    if var not in df.columns:
                        continue
                    codes = as_clean_string(df[var])
                    bad = codes.ne("") & (~codes.isin(allowed_codes))
                    if bad.any():
                        add_result(
                            rows,
                            survey_id,
                            "Labour",
                            "labour.isco_not_in_universe",
                            var,
                            f"{var} has ISCO codes not in ISCO universe",
                            1,
                            failed_n=int(bad.sum()),
                            denominator=n_obs,
                        )

        # 8.23 wage-unit pair completeness
        for wage_var, unit_var in parse_pairs(varlists.get("wage_and_unit", [])):
            has_wage = wage_var in df.columns
            has_unit = unit_var in df.columns
            if has_wage and not has_unit:
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.wage_without_unit_var",
                    f"{wage_var} {unit_var}",
                    f"There is {wage_var} info but no {unit_var} info",
                    1,
                    failed_n=None,
                    failed_ratio=np.nan,
                )
            if has_unit and not has_wage:
                add_result(
                    rows,
                    survey_id,
                    "Labour",
                    "labour.unit_without_wage_var",
                    f"{wage_var} {unit_var}",
                    f"There is {unit_var} info but no {wage_var} info",
                    1,
                    failed_n=None,
                    failed_ratio=np.nan,
                )

    if custom_rules_path is not None and custom_rules_path.exists():
        run_custom_rules(df, survey_id, custom_rules_path, rows)

    if not rows:
        return pd.DataFrame(
            columns=[
                "survey_id",
                "module",
                "check_id",
                "variable",
                "description",
                "severity",
                "failed_n",
                "failed_ratio",
            ]
        )

    out = pd.DataFrame([asdict(x) for x in rows])
    out = out.sort_values(["module", "check_id", "variable"], kind="stable").reset_index(drop=True)
    return out


def find_dataset(repo_root: Path, year: int, quarter: int) -> Path:
    cfg = load_version_config(repo_root)
    qroot = quarter_root(repo_root, cfg, year, quarter)
    dataset = harm_output_path(qroot, cfg, year)
    if dataset.exists():
        return dataset

    existing_harm_dir = resolve_existing_harm_dir(qroot, cfg, year)
    if existing_harm_dir is None:
        return dataset

    candidates = sorted(
        existing_harm_dir.joinpath("Data", "Harmonized").glob(f"{cfg.country}_{year}_{cfg.survey}_*_ALL.dta")
    )
    return candidates[-1] if candidates else dataset


def discover_datasets(
    repo_root: Path,
    start_year: int,
    end_year: int,
    quarters: list[int],
    include_2020q2: bool,
) -> list[tuple[int, int, Path]]:
    jobs: list[tuple[int, int, Path]] = []
    for year in range(start_year, end_year + 1):
        for quarter in quarters:
            if not include_2020q2 and year == 2020 and quarter == 2:
                continue
            path = find_dataset(repo_root, year, quarter)
            if path.exists():
                jobs.append((year, quarter, path))
    return jobs


def write_outputs(
    out_dir: Path,
    survey_id: str,
    reports: dict[str, pd.DataFrame],
    write_xlsx: bool,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    for key, frame in reports.items():
        out_csv = out_dir / f"{survey_id}_qcheck_{key}_py.csv"
        frame.to_csv(out_csv, index=False)

    if write_xlsx:
        out_xlsx = out_dir / f"{survey_id}_qcheck_py.xlsx"
        with pd.ExcelWriter(out_xlsx, engine="openpyxl") as writer:
            for key, frame in reports.items():
                frame.to_excel(writer, sheet_name=key[:31], index=False)


def run_one_dataset(
    dataset_path: Path,
    out_dir: Path,
    selected_reports: set[str],
    profile: str,
    varlists: dict[str, list[str]],
    isic_universe: dict[str, set[str]],
    isco_universe: dict[str, set[str]],
    weight_var: str,
    categoric_vars_arg: list[str] | None,
    max_categories: int,
    custom_rules_path: Path | None,
    write_xlsx: bool,
) -> dict[str, Any]:
    survey_id = dataset_path.stem
    df = pd.read_stata(dataset_path, convert_categoricals=False)
    df = normalize_columns(df)

    reports: dict[str, pd.DataFrame] = {}

    if "static" in selected_reports:
        reports["static"] = run_static_report(
            df,
            survey_id=survey_id,
            dataset_path=dataset_path,
            varlists=varlists,
            profile=profile,
            isic_universe=isic_universe,
            isco_universe=isco_universe,
            custom_rules_path=custom_rules_path,
        )

    if "basic" in selected_reports:
        reports["basic"] = run_basic_report(df, survey_id=survey_id, weight_var=weight_var)

    if "categoric" in selected_reports:
        categoric_vars = categoric_vars_arg or infer_categoric_vars(df, weight_var=weight_var, max_categories=max_categories)
        reports["categoric"] = run_categoric_report(
            df,
            survey_id=survey_id,
            weight_var=weight_var,
            categoric_vars=categoric_vars,
        )

    write_outputs(out_dir=out_dir, survey_id=survey_id, reports=reports, write_xlsx=write_xlsx)

    summary = {
        "survey_id": survey_id,
        "dataset": str(dataset_path),
        "output_dir": str(out_dir),
        "rows": {k: int(v.shape[0]) for k, v in reports.items()},
    }
    return summary


def main() -> int:
    args = parse_args()

    repo_root = Path(args.repo_root).resolve()
    out_root = Path(args.out_root).resolve()
    varlists_do = Path(args.varlists_do).resolve()
    isic_codes = Path(args.isic_codes).resolve()
    isco_codes = Path(args.isco_codes).resolve()
    custom_rules_path = Path(args.custom_rules).resolve() if args.custom_rules else None

    selected_reports = {x.lower() for x in split_csv(args.reports)}
    valid_reports = {"static", "basic", "categoric"}
    invalid_reports = selected_reports - valid_reports
    if invalid_reports:
        raise ValueError(f"Invalid report type(s): {sorted(invalid_reports)}")

    quarters = parse_quarters(args.quarters)
    categoric_vars_arg = [v.lower() for v in split_csv(args.categoric_vars)] if args.categoric_vars else None

    if not varlists_do.exists():
        raise FileNotFoundError(f"Varlist file not found: {varlists_do}")

    varlists = load_varlists(varlists_do)
    isic_universe = load_code_universe(isic_codes)
    isco_universe = load_code_universe(isco_codes)

    jobs: list[tuple[int | None, int | None, Path]] = []
    if args.dataset:
        dataset = Path(args.dataset).resolve()
        if not dataset.exists():
            raise FileNotFoundError(f"Dataset not found: {dataset}")
        jobs = [(None, None, dataset)]
    else:
        if not args.batch:
            raise ValueError("Use --dataset for a single file or --batch for multiple files")
        jobs = [
            (y, q, p)
            for (y, q, p) in discover_datasets(
                repo_root=repo_root,
                start_year=args.start_year,
                end_year=args.end_year,
                quarters=quarters,
                include_2020q2=args.include_2020q2,
            )
        ]

    if not jobs:
        print("No datasets found for the requested selection.")
        return 0

    failures: list[dict[str, str]] = []
    summaries: list[dict[str, Any]] = []

    for year, quarter, dataset_path in jobs:
        try:
            if year is not None and quarter is not None:
                out_dir = out_root / "by-year" / str(year) / f"Q{quarter}"
                label = f"{year}-Q{quarter}"
            else:
                out_dir = out_root / "single"
                label = dataset_path.stem

            print(f"[RUN] {label}: {dataset_path}")
            summary = run_one_dataset(
                dataset_path=dataset_path,
                out_dir=out_dir,
                selected_reports=selected_reports,
                profile=args.profile,
                varlists=varlists,
                isic_universe=isic_universe,
                isco_universe=isco_universe,
                weight_var=args.weight_var.lower(),
                categoric_vars_arg=categoric_vars_arg,
                max_categories=args.max_categories,
                custom_rules_path=custom_rules_path,
                write_xlsx=args.xlsx,
            )
            summaries.append(summary)
            print(f"[OK ] {label}: {summary['rows']}")
        except Exception as exc:  # noqa: BLE001
            failures.append({"dataset": str(dataset_path), "error": str(exc)})
            print(f"[ERR] {dataset_path}: {exc}", file=sys.stderr)

    summary_path = out_root / "run_summary.json"
    payload = {
        "jobs": len(jobs),
        "succeeded": len(summaries),
        "failed": len(failures),
        "summaries": summaries,
        "failures": failures,
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Summary: {summary_path}")

    if failures and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
