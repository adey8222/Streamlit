"""Shared pandas logic and Plotly figure builders — used by Streamlit and Dash dashboards."""

from __future__ import annotations

import functools
import os
import re
from pathlib import Path
from typing import BinaryIO

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from collections.abc import Mapping
from pandas.io.formats.style import Styler


def resolve_data_path() -> Path:
    env = os.environ.get("BEVERAGE_FACTORY_XLSX")
    if env:
        return Path(env).expanduser()
    here = Path(__file__).resolve().parent
    candidate = here / "beverage_factory_employee_dataset.xlsx"
    if candidate.exists():
        return candidate
    return Path("/Users/arun.dey/Desktop/beverage_factory_employee_dataset.xlsx")


STREAMLIT_UPLOADED_DF_KEY = "bf_uploaded_employees_df"
STREAMLIT_UPLOADED_NAME_KEY = "bf_uploaded_filename"

EMPLOYEE_REQUIRED_COLUMNS: tuple[str, ...] = (
    "Start Date",
    "Departure Date",
    "Department",
    "Terminated Reason",
    "User Status",
)


def prepare_employees_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Strip headers, validate required columns, parse dates — shared by Excel and CSV loads."""
    out = df.copy()
    out.columns = out.columns.astype(str).str.strip()
    missing = [c for c in EMPLOYEE_REQUIRED_COLUMNS if c not in out.columns]
    if missing:
        raise ValueError(
            "Missing required column(s): "
            + ", ".join(missing)
            + ". Use the same headers as the **Employees** sheet export "
            + "(**Quick Quits** is optional and defaults to blank)."
        )
    if "Quick Quits" not in out.columns:
        out["Quick Quits"] = ""

    out["Start Date"] = pd.to_datetime(out["Start Date"], errors="coerce")
    out["Departure Date"] = pd.to_datetime(out["Departure Date"], errors="coerce")

    out["Department"] = out["Department"].fillna("(Unknown)")
    out["Terminated Reason"] = out["Terminated Reason"].fillna("(Unknown)")
    out["Quick Quits"] = out["Quick Quits"].astype(str).str.strip()

    out["hire_period"] = out["Start Date"].dt.to_period("M")
    out["departure_period"] = out["Departure Date"].dt.to_period("M")

    return out


@functools.lru_cache(maxsize=2)
def load_employees(path_str: str) -> pd.DataFrame:
    df = pd.read_excel(path_str, sheet_name="Employees", engine="openpyxl")
    return prepare_employees_dataframe(df)


def load_employees_csv(source: str | Path | BinaryIO) -> pd.DataFrame:
    """Load roster rows from CSV (UTF-8). ``source`` may be a path or a Streamlit ``UploadedFile`` / buffer."""
    df = pd.read_csv(source)
    return prepare_employees_dataframe(df)


# Common in HR extracts: reason text ends with "(V)" / "(I)" for voluntary vs involuntary.
_RE_SUFFIX_VOLUNTARY = re.compile(r"\(\s*v\s*\)\s*$", re.IGNORECASE)
_RE_SUFFIX_INVOLUNTARY = re.compile(r"\(\s*i\s*\)\s*$", re.IGNORECASE)

MONTH_LABELS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def period_column_labels(valid_periods: pd.PeriodIndex) -> list[str]:
    """Stable English labels (avoids locale-specific ``%b`` quirks / ambiguous duplicates)."""
    return [f"{MONTH_LABELS[p.month - 1]} '{p.year % 100:02d}" for p in valid_periods]


def last_n_month_periods(reference: pd.Timestamp, n: int = 12) -> pd.PeriodIndex:
    end = reference.to_period("M")
    start = end - (n - 1)
    return pd.period_range(start=start, end=end, freq="M")


def filter_period_in_range(
    series_period: pd.Series, valid: pd.PeriodIndex
) -> pd.Series:
    return series_period.isin(valid)


def stacked_monthly_by_department(
    df: pd.DataFrame,
    period_col: str,
    valid_periods: pd.PeriodIndex,
) -> pd.DataFrame:
    sub = df[filter_period_in_range(df[period_col], valid_periods)].copy()
    if sub.empty:
        return pd.DataFrame()
    g = (
        sub.groupby([period_col, "Department"], observed=False)
        .size()
        .reset_index(name="count")
    )
    wide = g.pivot(index=period_col, columns="Department", values="count").fillna(0)
    wide = wide.reindex(valid_periods, fill_value=0)
    return wide


def yoy_monthly_counts(
    df: pd.DataFrame,
    date_col: str,
    years: tuple[int, int],
    *,
    clip_future_months_as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Calendar-month counts per year (index 1–12). Future months optional NaN vs sidebar reference."""
    out: dict[str, list[float]] = {}
    d = df[df[date_col].notna()].copy()
    cutoff: pd.Period | None = None
    if clip_future_months_as_of is not None:
        cutoff = pd.Timestamp(clip_future_months_as_of).normalize().to_period("M")

    for y in (int(years[0]), int(years[1])):
        sub = d[d[date_col].dt.year == y]
        counts = sub.groupby(sub[date_col].dt.month, observed=False).size()
        filled = counts.reindex(range(1, 13), fill_value=0).astype(float)
        if cutoff is None:
            out[str(y)] = filled.tolist()
            continue
        col_vals: list[float] = []
        for m in range(1, 13):
            cell = pd.Period(f"{y}-{m:02d}", freq="M")
            if cell > cutoff:
                col_vals.append(float("nan"))
            else:
                col_vals.append(float(filled.loc[m]))
        out[str(y)] = col_vals
    return pd.DataFrame(out, index=range(1, 13))


def department_month_matrix(
    df: pd.DataFrame,
    period_col: str,
    valid_periods: pd.PeriodIndex,
) -> pd.DataFrame:
    """Rows = departments, columns = labelled months (rolling window). Integer counts."""
    wide = stacked_monthly_by_department(df, period_col, valid_periods)
    if wide.empty:
        return pd.DataFrame()
    mt = wide.transpose().astype(int)
    mt.columns = period_column_labels(valid_periods)
    mt.index.name = "Department"
    return mt.sort_index()


def department_month_matrix_full_roster(
    df: pd.DataFrame,
    period_col: str,
    valid_periods: pd.PeriodIndex,
    roster_departments: pd.Index | list[str],
) -> pd.DataFrame:
    """Same as ``department_month_matrix`` but includes every roster department (zeros where no exits)."""
    labels = period_column_labels(valid_periods)
    idx_sorted = pd.Index(sorted({str(x) for x in roster_departments}))
    base = department_month_matrix(df, period_col, valid_periods)
    if base.empty:
        out = pd.DataFrame(0, index=idx_sorted, columns=labels)
        out.index.name = "Department"
        return out.astype(int)
    aligned = base.reindex(idx_sorted, fill_value=0).astype(int)
    aligned.columns = labels
    aligned.index.name = "Department"
    return aligned


def termination_reason_month_matrix(
    departures: pd.DataFrame,
    valid_periods: pd.PeriodIndex,
    roster_reasons: pd.Index | list[str],
) -> pd.DataFrame:
    """Rows = terminated reason (full roster), columns = months; inactive departures in the rolling window."""
    labels = period_column_labels(valid_periods)
    idx_sorted = pd.Index(sorted({str(x) for x in roster_reasons}))
    sub = departures[
        filter_period_in_range(departures["departure_period"], valid_periods)
    ].copy()
    if sub.empty:
        out = pd.DataFrame(0, index=idx_sorted, columns=labels)
        out.index.name = "Terminated Reason"
        return out.astype(int)
    g = (
        sub.groupby(["Terminated Reason", "departure_period"], observed=False)
        .size()
        .reset_index(name="count")
    )
    wide = g.pivot(
        index="Terminated Reason", columns="departure_period", values="count"
    ).fillna(0)
    wide = wide.reindex(columns=valid_periods, fill_value=0).astype(int)
    wide.columns = labels
    aligned = wide.reindex(idx_sorted, fill_value=0).astype(int)
    aligned.index.name = "Terminated Reason"
    return aligned


def headcount_department_month_matrix(
    rh: pd.DataFrame,
    valid_periods: pd.PeriodIndex,
) -> pd.DataFrame:
    """End-of-month active headcount by dept × month for months in ``valid_periods``."""
    if rh.empty:
        return pd.DataFrame()
    dept_cols = [c for c in rh.columns if c not in ("month_end", "_total")]
    tmp = rh.copy()
    tmp["period"] = tmp["month_end"].dt.to_period("M")
    mask = tmp["period"].isin(valid_periods)
    sub = tmp.loc[mask, dept_cols + ["period"]].set_index("period")
    sub = sub.reindex(valid_periods, fill_value=0).astype(int)
    mt = sub.transpose()
    mt.columns = period_column_labels(valid_periods)
    mt.index.name = "Department"
    return mt.sort_index()


def classify_exit_type(reason: object) -> str:
    """Bucket inactive exits into Involuntary / Voluntary / Other using ``Terminated Reason`` text."""
    s = str(reason).strip().lower()
    if not s or s in ("(unknown)", "nan"):
        return "Other"
    # Suffix markers e.g. ``better opp (V)``, ``Unsatisfactory work (I)`` (checked before substring "voluntary").
    if _RE_SUFFIX_VOLUNTARY.search(s):
        return "Voluntary"
    if _RE_SUFFIX_INVOLUNTARY.search(s):
        return "Involuntary"
    if "involuntary" in s:
        return "Involuntary"
    if "voluntary" in s:
        return "Voluntary"
    invol_kw = (
        "layoff",
        "rif",
        "reduction in force",
        "position eliminated",
        "job eliminated",
        "misconduct",
        "performance",
        "termination — employer",
        "terminated by employer",
        "involuntary",
    )
    vol_kw = (
        "resignation",
        "resigned",
        "quit",
        "retired",
        "retirement",
        "personal reasons",
        "another job",
        "new position",
        "voluntary",
    )
    if any(k in s for k in invol_kw):
        return "Involuntary"
    if any(k in s for k in vol_kw):
        return "Voluntary"
    return "Other"


def departures_for_exit_class(departures: pd.DataFrame, exit_class: str) -> pd.DataFrame:
    """Inactive exits whose ``Terminated Reason`` maps to Involuntary or Voluntary (not Other)."""
    if departures.empty:
        return departures
    sub = departures.copy()
    bucket = sub["Terminated Reason"].map(classify_exit_type)
    return sub[bucket.eq(exit_class)].copy()


def exit_type_month_matrix(
    departures: pd.DataFrame,
    valid_periods: pd.PeriodIndex,
) -> pd.DataFrame:
    """Rows = Involuntary / Voluntary / Other, columns = months."""
    sub = departures[
        filter_period_in_range(departures["departure_period"], valid_periods)
    ].copy()
    if sub.empty:
        return pd.DataFrame()
    sub = sub[sub["Departure Date"].notna()].copy()
    sub["exit_type"] = sub["Terminated Reason"].map(classify_exit_type)
    g = (
        sub.groupby(["exit_type", "departure_period"], observed=False)
        .size()
        .reset_index(name="count")
    )
    wide = g.pivot(index="exit_type", columns="departure_period", values="count").fillna(
        0
    )
    if wide.empty:
        return pd.DataFrame()
    preferred = ("Involuntary", "Voluntary", "Other")
    idx = [r for r in preferred if r in wide.index] + [
        r for r in wide.index if r not in preferred
    ]
    wide = wide.reindex(idx).fillna(0)
    wide = wide.reindex(columns=valid_periods, fill_value=0).astype(int)
    wide.columns = period_column_labels(valid_periods)
    wide.index.name = "Exit type"
    return wide


def running_headcount_by_department(
    df: pd.DataFrame, reference: pd.Timestamp
) -> pd.DataFrame:
    first = df["Start Date"].min()
    if pd.isna(first):
        return pd.DataFrame()
    month_starts = pd.date_range(
        first.to_period("M").to_timestamp(how="start"),
        reference.to_period("M").to_timestamp(how="start"),
        freq="MS",
    )
    month_ends = month_starts + pd.offsets.MonthEnd(0)

    rows = []
    depts = sorted(df["Department"].dropna().unique().tolist())
    for me in month_ends:
        mask = (df["Start Date"] <= me) & (
            df["Departure Date"].isna() | (df["Departure Date"] > me)
        )
        part = df.loc[mask]
        counts = part.groupby("Department", observed=False).size()
        row = {"month_end": me, "_total": int(len(part))}
        for dep in depts:
            row[dep] = int(counts.get(dep, 0))
        rows.append(row)
    return pd.DataFrame(rows)


def total_headcount_yoy_monthly(
    df: pd.DataFrame,
    years: tuple[int, int],
    *,
    clip_future_months_as_of: pd.Timestamp | None = None,
) -> pd.DataFrame:
    """Total roster count at each calendar month-end, by year — same rules as running headcount.

    Rows are calendar months **1–12** (aligned with ``MONTH_LABELS`` in ``plot_yoy_lines``).
    Columns are ``str(year)`` for each year in ``years``.

    If ``clip_future_months_as_of`` is set, any calendar month **after** that timestamp's month
    (same month inclusive through month-end) is stored as NaN for each year column. That avoids a
    flat line for "future" months on a point-in-time roster extract (counts would otherwise repeat
    the latest snapshot).
    """
    y1, y2 = int(years[0]), int(years[1])
    cutoff: pd.Period | None = None
    if clip_future_months_as_of is not None:
        cutoff = pd.Timestamp(clip_future_months_as_of).normalize().to_period("M")
    out: dict[str, list[float]] = {}
    for y in (y1, y2):
        vals: list[float] = []
        for m in range(1, 13):
            if cutoff is not None:
                cell = pd.Period(f"{y}-{m:02d}", freq="M")
                if cell > cutoff:
                    vals.append(float("nan"))
                    continue
            me = month_end_timestamp(y, m)
            mask = df["Start Date"].notna() & (df["Start Date"] <= me) & (
                df["Departure Date"].isna() | (df["Departure Date"] > me)
            )
            vals.append(float(mask.sum()))
        out[str(y)] = vals
    return pd.DataFrame(out, index=range(1, 13))


def average_active_tenure_years(df: pd.DataFrame, reference: pd.Timestamp) -> float:
    """Mean tenure in **calendar years** for **currently active employees only**.

    For each active row: tenure = (reference date − hire date) ÷ 365.25 days per year.
    Excludes missing start dates and hires after the reference date.
    """
    ref = pd.Timestamp(reference).normalize()
    mask = df["User Status"].astype(str).str.strip().str.lower().eq("active")
    active = df.loc[mask].copy()
    if active.empty:
        return float("nan")

    starts = pd.to_datetime(active["Start Date"], errors="coerce").dt.normalize()
    ok = starts.notna() & (starts <= ref)
    if not ok.any():
        return float("nan")

    days = (ref - starts[ok]).dt.days.astype(float).clip(lower=0)
    years = days / 365.25
    return float(years.mean())


def format_tenure_years_display(years_mean: float | None) -> str:
    """Format mean tenure in years with one decimal (e.g. 3.4, 2.5)."""
    if years_mean is None or pd.isna(years_mean):
        return "—"
    return f"{float(years_mean):.1f}"


def format_count_display(n: int | float | None) -> str:
    """Whole-number KPI with grouping (e.g. 1,100)."""
    if n is None:
        return "—"
    try:
        v = float(n)
        if pd.isna(v):
            return "—"
        return f"{int(round(v)):,}"
    except (TypeError, ValueError):
        return "—"


def month_end_timestamp(year: int, month: int) -> pd.Timestamp:
    """Last calendar day of ``month`` / ``year`` (normalized, naive)."""
    first = pd.Timestamp(year=int(year), month=int(month), day=1)
    return (first + pd.offsets.MonthEnd(0)).normalize()


def snapshot_metrics(df: pd.DataFrame, reference: pd.Timestamp) -> dict[str, float | int]:
    """Headline KPIs anchored to ``reference`` (same 12‑month window as charts)."""
    ref = pd.Timestamp(reference).normalize()
    periods = last_n_month_periods(ref, 12)

    tenure_years = average_active_tenure_years(df, ref)

    status = df["User Status"].astype(str).str.strip().str.lower()
    active_count = int((status == "active").sum())
    inactive_count = int((status == "inactive").sum())

    hires = df[df["Start Date"].notna()].copy()
    hires_l12 = int(filter_period_in_range(hires["hire_period"], periods).sum())

    inactive_dated = df[status.eq("inactive") & df["Departure Date"].notna()].copy()
    exits_l12 = int(
        filter_period_in_range(inactive_dated["departure_period"], periods).sum()
    )

    qq_mask = inactive_dated["Quick Quits"].astype(str).str.strip().str.upper() == "YES"
    qq = inactive_dated.loc[qq_mask]
    qq_l12 = int(filter_period_in_range(qq["departure_period"], periods).sum())

    net_change_l12 = hires_l12 - exits_l12

    return {
        "tenure_years": tenure_years,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "total_count": int(len(df)),
        "hires_last_12": hires_l12,
        "departures_last_12": exits_l12,
        "quick_quits_last_12": qq_l12,
        "net_change_last_12": net_change_l12,
    }


def snapshot_metrics_as_of(df: pd.DataFrame, reference: pd.Timestamp) -> dict[str, float | int]:
    """Headline KPIs as of **month-end** ``reference``: roster from hire/departure dates; L12M ends that month.

    Row 1 uses who had **started on or before** that month-end and whether they had **left on or before**
    that date (vs ``User Status`` on the extract). Row 2 uses the same rolling 12 calendar months as charts.
    """
    ref = pd.Timestamp(reference).normalize()
    ref = month_end_timestamp(ref.year, ref.month)
    periods = last_n_month_periods(ref, 12)

    starts = pd.to_datetime(df["Start Date"], errors="coerce").dt.normalize()
    deps = pd.to_datetime(df["Departure Date"], errors="coerce").dt.normalize()

    joined = starts.notna() & (starts <= ref)
    employed = joined & (deps.isna() | (deps > ref))
    departed = joined & deps.notna() & (deps <= ref)

    active_count = int(employed.sum())
    inactive_count = int(departed.sum())
    total_count = int(joined.sum())

    active_df = df.loc[employed].copy()
    if active_df.empty:
        tenure_years = float("nan")
    else:
        hs = pd.to_datetime(active_df["Start Date"], errors="coerce").dt.normalize()
        ok = hs.notna() & (hs <= ref)
        if not ok.any():
            tenure_years = float("nan")
        else:
            days = (ref - hs[ok]).dt.days.astype(float).clip(lower=0)
            tenure_years = float((days / 365.25).mean())

    hires = df[df["Start Date"].notna()].copy()
    hires_l12 = int(filter_period_in_range(hires["hire_period"], periods).sum())

    status = df["User Status"].astype(str).str.strip().str.lower()
    inactive_dated = df[status.eq("inactive") & df["Departure Date"].notna()].copy()
    exits_l12 = int(
        filter_period_in_range(inactive_dated["departure_period"], periods).sum()
    )

    qq_mask = inactive_dated["Quick Quits"].astype(str).str.strip().str.upper() == "YES"
    qq = inactive_dated.loc[qq_mask]
    qq_l12 = int(filter_period_in_range(qq["departure_period"], periods).sum())

    net_change_l12 = hires_l12 - exits_l12

    return {
        "tenure_years": tenure_years,
        "active_count": active_count,
        "inactive_count": inactive_count,
        "total_count": total_count,
        "hires_last_12": hires_l12,
        "departures_last_12": exits_l12,
        "quick_quits_last_12": qq_l12,
        "net_change_last_12": net_change_l12,
    }


# Harmony-first palette on dark canvases (Tailwind-informed)
_SERIES_COLORS = [
    "#38bdf8",
    "#818cf8",
    "#34d399",
    "#f472b6",
    "#fcd34d",
    "#fb923c",
    "#2dd4bf",
    "#a78bfa",
    "#fbbf24",
    "#e879f9",
    "#4ade80",
    "#60a5fa",
]


def finalize_figure(
    fig: go.Figure,
    *,
    height: int,
    legend_right: bool = False,
    pie: bool = False,
) -> go.Figure:
    grid = "rgba(148, 163, 184, 0.12)"
    line = "rgba(148, 163, 184, 0.35)"
    text = "#e2e8f0"
    muted = "#94a3b8"
    accent = "#38bdf8"

    fig.update_layout(
        template="plotly_dark",
        height=height,
        # Keep charts fixed when dragging / scrolling (toolbar zoom still available if needed).
        dragmode=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(8,12,26,0.35)",
        font=dict(color=text, size=12, family="ui-sans-serif, system-ui, sans-serif"),
        title=dict(
            font=dict(
                size=14,
                family="ui-sans-serif, system-ui, sans-serif",
                color="#f1f5f9",
            ),
            pad=dict(b=12, l=4),
            xanchor="left",
            x=0.01,
            xref="paper",
        ),
        margin=dict(t=54, r=36 if legend_right else 24, l=54, b=64),
        hoverlabel=dict(
            bgcolor="rgba(15,23,42,0.95)",
            bordercolor=accent,
            font=dict(color="#f8fafc", family="ui-sans-serif, system-ui, sans-serif", size=12),
            align="left",
        ),
    )

    if not pie:
        axis_kwargs = dict(
            gridcolor=grid,
            zeroline=False,
            zerolinewidth=1,
            showline=False,
            showgrid=True,
            linewidth=1,
            linecolor=line,
            tickfont=dict(color=muted, size=11),
            title=dict(font=dict(color=muted, size=11, weight=500)),
        )
        fig.update_xaxes(**axis_kwargs)
        fig.update_yaxes(**axis_kwargs)

    lg_base = dict(
        bgcolor="rgba(15,23,42,0.84)",
        bordercolor="rgba(148,163,184,0.22)",
        borderwidth=1,
        font=dict(color=muted, size=11),
        title=dict(font=dict(color="#cbd5e1", size=11)),
    )
    if legend_right:
        fig.update_layout(
            legend=dict(**lg_base, orientation="v", yanchor="top", y=1, xanchor="left", x=1.02),
        )
    elif not pie:
        fig.update_layout(legend=dict(**lg_base))

    if pie:
        fig.update_layout(
            showlegend=True,
            legend=dict(**lg_base),
        )

    return fig


def plot_stacked_monthly(wide: pd.DataFrame, title: str) -> go.Figure:
    if wide.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=title)
        return finalize_figure(fig, height=460, legend_right=True)

    xlabs = wide.index.astype(str).tolist()
    fig = go.Figure()
    for i, dep in enumerate(wide.columns):
        col = _SERIES_COLORS[i % len(_SERIES_COLORS)]
        fig.add_trace(
            go.Bar(
                name=str(dep),
                x=xlabs,
                y=wide[dep].tolist(),
                marker=dict(
                    color=col,
                    line=dict(width=0, color="rgba(248,250,252,0.06)"),
                    cornerradius=3,
                ),
            )
        )
    fig.update_layout(
        title=title,
        barmode="stack",
        xaxis_title="Month",
        yaxis_title="Count",
        legend_title="Department",
        bargap=0.15,
    )
    return finalize_figure(fig, height=460, legend_right=True)


def _yoy_prior_year_column(yoy_df: pd.DataFrame, forecast_year_col: str) -> str | None:
    """Other YoY column when exactly two year columns exist (e.g. ``2025`` vs ``2026``)."""
    fc = str(forecast_year_col)
    cols = [str(c) for c in yoy_df.columns]
    if fc not in cols:
        return None
    others = [c for c in cols if c != fc]
    if len(others) == 1:
        return others[0]
    try:
        prev = str(int(fc) - 1)
        return prev if prev in cols else None
    except ValueError:
        return None


def _seasonal_step_from_prior_year(
    yoy_df: pd.DataFrame,
    *,
    prior_col: str,
    anchor_month: int,
    forward_month: int,
    cur_anchor: float,
) -> float | None:
    """Additive shift using prior calendar year: actual + (prior[fw] − prior[anchor])."""
    pa = yoy_df.loc[anchor_month, prior_col]
    pm = yoy_df.loc[forward_month, prior_col]
    if pd.isna(pa) or pd.isna(pm):
        return None
    return max(0.0, float(cur_anchor) + (float(pm) - float(pa)))


def _partial_year_linear_forecast(
    yoy_df: pd.DataFrame,
    year_col: str,
    last_actual_month: int,
    horizon: int,
) -> tuple[list[int], list[float]] | None:
    """Extend counts through ``last_actual_month`` with a naive outlook ahead.

    Fits a least-squares line on completed months in the **forecast year** (≥2 points); otherwise
    carries the latest month flat.

    Forward months **blend** (~40% regression / ~60% prior-year seasonality when available): same
    calendar pattern as the other YoY column anchored at the latest actual (e.g. 2025 May–Jul
    deltas applied from April 2026 actual). Short swings in the current year alone no longer drive
    the whole outlook.

    Still applies a soft multiplicative floor from the latest actual so projections do not collapse
    toward zero from noise alone.
    """
    lin_w = 0.42

    if horizon < 1 or last_actual_month < 1 or last_actual_month >= 12:
        return None
    col = str(year_col)
    if col not in yoy_df.columns:
        return None
    prior_col = _yoy_prior_year_column(yoy_df, col)

    xs: list[float] = []
    ys: list[float] = []
    for m in range(1, last_actual_month + 1):
        v = yoy_df.loc[m, col]
        if pd.isna(v):
            return None
        xs.append(float(m))
        ys.append(float(v))
    if len(xs) < 1:
        return None

    months_o: list[int] = []
    preds: list[float] = []
    y_last = float(ys[-1])

    if len(xs) >= 2:
        coef = np.polyfit(np.asarray(xs), np.asarray(ys), 1)
        poly = np.poly1d(coef)
        for k in range(1, horizon + 1):
            m = last_actual_month + k
            if m > 12:
                break
            months_o.append(m)
            linear_pred = max(0.0, float(poly(float(m))))
            seasonal_pred: float | None = None
            if prior_col is not None:
                seasonal_pred = _seasonal_step_from_prior_year(
                    yoy_df,
                    prior_col=prior_col,
                    anchor_month=last_actual_month,
                    forward_month=m,
                    cur_anchor=y_last,
                )
            if seasonal_pred is None:
                combined = linear_pred
            else:
                combined = lin_w * linear_pred + (1.0 - lin_w) * seasonal_pred

            if y_last <= 0.5:
                preds.append(combined)
            else:
                decay_floor = max(1.0, y_last * (0.78**k))
                preds.append(max(combined, decay_floor))
    else:
        flat = max(0.0, float(ys[0]))
        for k in range(1, horizon + 1):
            m = last_actual_month + k
            if m > 12:
                break
            months_o.append(m)
            seasonal_pred: float | None = None
            if prior_col is not None:
                seasonal_pred = _seasonal_step_from_prior_year(
                    yoy_df,
                    prior_col=prior_col,
                    anchor_month=last_actual_month,
                    forward_month=m,
                    cur_anchor=flat,
                )
            if seasonal_pred is None:
                combined = flat
            else:
                combined = lin_w * flat + (1.0 - lin_w) * seasonal_pred
            if flat <= 0.5:
                preds.append(combined)
            else:
                decay_floor = max(1.0, flat * (0.78**k))
                preds.append(max(combined, decay_floor))
    return (months_o, preds) if months_o else None


def blank_yoy_outlook_figure(
    message: str = "Outlook is shown only for **Rolling last 12 months** with a reference month before December.",
) -> go.Figure:
    """Dash-friendly placeholder when YoY outlook is not computed."""
    fig = go.Figure()
    fig.add_annotation(
        text=message.replace("**", ""),
        xref="paper",
        yref="paper",
        x=0.5,
        y=0.55,
        showarrow=False,
        font=dict(size=12, color="#64748b", family="ui-sans-serif, system-ui, sans-serif"),
    )
    fig.update_layout(title="Trend outlook")
    return finalize_figure(fig, height=260)


def plot_yoy_outlook_figure(
    yoy_df: pd.DataFrame,
    *,
    title: str,
    y_label: str,
    trend_forecast_for_year: int,
    trend_forecast_last_month: int,
    trend_forecast_horizon: int = 3,
) -> go.Figure | None:
    """Standalone dashed outlook (same math as ``plot_yoy_lines`` embed)."""
    if yoy_df is None or yoy_df.empty:
        return None
    fc = _partial_year_linear_forecast(
        yoy_df,
        str(trend_forecast_for_year),
        int(trend_forecast_last_month),
        int(trend_forecast_horizon),
    )
    if fc is None:
        return None
    line_colors = ["#22d3ee", "#c084fc"]
    months_o, preds = fc
    cols_list = [str(c) for c in yoy_df.columns]
    try:
        fc_idx = cols_list.index(str(trend_forecast_for_year))
    except ValueError:
        fc_idx = 0
    c_line = line_colors[fc_idx % len(line_colors)]
    lm = int(trend_forecast_last_month)
    y_last = float(yoy_df.loc[lm, str(trend_forecast_for_year)])
    x_bridge = [MONTH_LABELS[lm - 1]] + [MONTH_LABELS[m - 1] for m in months_o]
    y_bridge = [y_last] + preds
    lbl_bridge = [""] + [str(int(round(p))) for p in preds]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=x_bridge,
            y=y_bridge,
            mode="lines+markers+text",
            name=f"{trend_forecast_for_year} outlook",
            text=lbl_bridge,
            textposition="top center",
            textfont=dict(
                color="#94a3b8",
                size=10,
                family="ui-sans-serif, system-ui, sans-serif",
            ),
            cliponaxis=False,
            line=dict(width=4.5, color=c_line, dash="dash"),
            marker=dict(
                size=10,
                color="rgba(15,23,42,0.65)",
                line=dict(width=2.5, color=c_line),
                opacity=1,
            ),
            hovertemplate="Outlook %{x}<br>%{y:.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        title=dict(
            text=(
                f"{title}<br>"
                "<sup style='font-size:11px;color:#94a3af;font-weight:400'>"
                "~42% regression on current-year actuals + ~58% same-calendar pattern from the prior YoY "
                "year (anchored at your latest month), with a conservative floor; illustrative only.</sup>"
            ),
            font=dict(
                size=14,
                family="ui-sans-serif, system-ui, sans-serif",
                color="#f1f5f9",
            ),
            pad=dict(b=8, l=4),
            xanchor="left",
            x=0.01,
            xref="paper",
        ),
        xaxis_title="Calendar month",
        yaxis_title=y_label,
        legend_title="Series",
        showlegend=True,
    )
    fig_out = finalize_figure(fig, height=360)
    fig_out.update_layout(margin=dict(t=72, b=70))
    return fig_out


def plot_yoy_lines(
    yoy_df: pd.DataFrame,
    title: str,
    y_label: str,
    *,
    trend_forecast_for_year: int | None = None,
    trend_forecast_last_month: int | None = None,
    trend_forecast_horizon: int = 3,
    embed_trend_forecast: bool = True,
) -> go.Figure:
    line_colors = ["#22d3ee", "#c084fc"]
    marker_colors = ["#bae6fd", "#e9d5ff"]
    if yoy_df is None or yoy_df.empty or len(yoy_df.columns) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=title)
        return finalize_figure(fig, height=420)

    fig = go.Figure()
    for idx, col in enumerate(yoy_df.columns):
        c_line = line_colors[idx % len(line_colors)]
        c_mark = marker_colors[idx % len(marker_colors)]
        ys = yoy_df[col].tolist()
        pt_labels = []
        for v in ys:
            if pd.isna(v):
                pt_labels.append("")
            else:
                pt_labels.append(str(int(round(float(v)))))
        fig.add_trace(
            go.Scatter(
                x=MONTH_LABELS,
                y=ys,
                mode="lines+markers+text",
                name=str(col),
                text=pt_labels,
                textposition="top center",
                textfont=dict(
                    color="#f8fafc",
                    size=11,
                    family="ui-sans-serif, system-ui, sans-serif",
                ),
                cliponaxis=False,
                connectgaps=False,
                line=dict(width=2.8, color=c_line, shape="linear"),
                marker=dict(
                    size=9,
                    color=c_mark,
                    line=dict(width=1.75, color=c_line),
                    opacity=0.95,
                ),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Calendar month",
        yaxis_title=y_label,
        legend_title="Year",
    )
    forecast_added = False
    if (
        embed_trend_forecast
        and trend_forecast_for_year is not None
        and trend_forecast_last_month is not None
        and trend_forecast_horizon >= 1
    ):
        fc = _partial_year_linear_forecast(
            yoy_df,
            str(trend_forecast_for_year),
            int(trend_forecast_last_month),
            int(trend_forecast_horizon),
        )
        if fc is not None:
            months_o, preds = fc
            cols_list = [str(c) for c in yoy_df.columns]
            try:
                fc_idx = cols_list.index(str(trend_forecast_for_year))
            except ValueError:
                fc_idx = 0
            c_line = line_colors[fc_idx % len(line_colors)]
            c_mark = marker_colors[fc_idx % len(marker_colors)]
            lm = int(trend_forecast_last_month)
            y_last = float(yoy_df.loc[lm, str(trend_forecast_for_year)])
            x_bridge = [MONTH_LABELS[lm - 1]] + [MONTH_LABELS[m - 1] for m in months_o]
            y_bridge = [y_last] + preds
            lbl_bridge = [""] + [str(int(round(p))) for p in preds]
            fig.add_trace(
                go.Scatter(
                    x=x_bridge,
                    y=y_bridge,
                    mode="lines+markers+text",
                    name=f"{trend_forecast_for_year} outlook",
                    text=lbl_bridge,
                    textposition="top center",
                    textfont=dict(
                        color="#94a3b8",
                        size=10,
                        family="ui-sans-serif, system-ui, sans-serif",
                    ),
                    cliponaxis=False,
                    line=dict(width=4.5, color=c_line, dash="dash"),
                    marker=dict(
                        size=10,
                        color="rgba(15,23,42,0.65)",
                        line=dict(width=2.5, color=c_line),
                        opacity=1,
                    ),
                    hovertemplate="Outlook %{x}<br>%{y:.0f}<extra></extra>",
                )
            )
            forecast_added = True

    fig_out = finalize_figure(fig, height=440 if forecast_added else 420)
    extra_top = 36 if forecast_added else 0
    fig_out.update_layout(margin=dict(t=54 + extra_top, b=70))
    if forecast_added:
        fig_out.update_layout(
            title=dict(
                text=(
                    f"{title}<br>"
                    "<sup style='font-size:11px;color:#94a3af;font-weight:400'>"
                    "Dashed trace = regression blend with prior-year seasonality · illustrative only · "
                    "shown only on <b>Rolling last 12 months</b></sup>"
                ),
                font=dict(
                    size=14,
                    family="ui-sans-serif, system-ui, sans-serif",
                    color="#f1f5f9",
                ),
                pad=dict(b=8, l=4),
                xanchor="left",
                x=0.01,
                xref="paper",
            ),
        )
    return fig_out


def plot_exit_type_month_lines(
    exit_mtx: pd.DataFrame | None,
    title: str,
    *,
    footnote: str | None = None,
) -> go.Figure:
    """Involuntary vs Voluntary inactive-exit counts by month (same window as exit-type × month grid)."""
    line_colors = ["#22d3ee", "#c084fc"]
    marker_colors = ["#bae6fd", "#e9d5ff"]
    series_names = ("Involuntary", "Voluntary")

    if exit_mtx is None or exit_mtx.empty or len(exit_mtx.columns) == 0:
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=title)
        return finalize_figure(fig, height=380)

    xlabs = [str(c) for c in exit_mtx.columns]
    fig = go.Figure()
    for idx, row_name in enumerate(series_names):
        c_line = line_colors[idx % len(line_colors)]
        c_mark = marker_colors[idx % len(marker_colors)]
        if row_name in exit_mtx.index:
            row = exit_mtx.loc[row_name]
            ys = [int(round(float(v))) if pd.notna(v) else 0 for v in row.tolist()]
        else:
            ys = [0] * len(xlabs)
        pt_labels = [str(v) for v in ys]
        fig.add_trace(
            go.Scatter(
                x=xlabs,
                y=ys,
                mode="lines+markers+text",
                name=row_name,
                text=pt_labels,
                textposition="top center",
                textfont=dict(
                    color="#f8fafc",
                    size=11,
                    family="ui-sans-serif, system-ui, sans-serif",
                ),
                cliponaxis=False,
                line=dict(width=2.8, color=c_line, shape="linear"),
                marker=dict(
                    size=9,
                    color=c_mark,
                    line=dict(width=1.75, color=c_line),
                    opacity=0.95,
                ),
            )
        )
    fig.update_layout(
        title=title,
        xaxis_title="Month",
        yaxis_title="Exits",
        legend_title="Exit type",
    )
    fig_out = finalize_figure(fig, height=380)
    fig_out.update_layout(margin=dict(t=58, b=64))
    if footnote:
        fig_out.add_annotation(
            xref="paper",
            yref="paper",
            x=0.01,
            y=0.99,
            xanchor="left",
            yanchor="top",
            text=f"<b>Note</b><br>{footnote}",
            showarrow=False,
            font=dict(size=10, color="#e2e8f0", family="ui-sans-serif, system-ui, sans-serif"),
            align="left",
            bgcolor="rgba(15,23,42,0.94)",
            bordercolor="rgba(148,163,184,0.38)",
            borderwidth=1,
            borderpad=8,
        )
    return fig_out


def plot_yoy_same_month_bars(
    yoy_df: pd.DataFrame,
    calendar_month: int,
    title: str,
    y_label: str,
) -> go.Figure:
    """Compare YoY counts for one calendar month only (one bar per year in ``yoy_df``)."""
    line_colors = ["#22d3ee", "#c084fc"]
    if yoy_df.empty or calendar_month not in range(1, 13):
        fig = go.Figure()
        fig.add_annotation(
            text="No data",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=title)
        return finalize_figure(fig, height=420)

    row = yoy_df.loc[calendar_month]
    years = [str(c) for c in yoy_df.columns]
    vals = [
        0 if pd.isna(row[c]) else int(round(float(row[c])))
        for c in yoy_df.columns
    ]
    cols = [line_colors[i % len(line_colors)] for i in range(len(vals))]
    fig = go.Figure(
        data=[
            go.Bar(
                x=years,
                y=vals,
                marker=dict(
                    color=cols,
                    line=dict(width=0, color="rgba(248,250,252,0.12)"),
                    cornerradius=4,
                ),
                text=vals,
                textposition="outside",
                textfont=dict(color="#e2e8f0", size=12),
            )
        ]
    )
    fig.update_layout(
        title=title,
        xaxis_title="Year",
        yaxis_title=y_label,
        bargap=0.35,
    )
    return finalize_figure(fig, height=420)


def plot_running_headcount(long_df: pd.DataFrame, depts: list[str]) -> go.Figure:
    fig = go.Figure()
    for i, dep in enumerate(depts):
        col = _SERIES_COLORS[i % len(_SERIES_COLORS)]
        fig.add_trace(
            go.Scatter(
                x=long_df["month_end"],
                y=long_df[dep],
                mode="lines",
                name=str(dep),
                stackgroup="one",
                line=dict(width=0.35, color="rgba(248,250,252,0.08)"),
                fillcolor=col,
                opacity=0.92,
            )
        )
    fig.update_layout(
        title="Running headcount (active) — stacked by department",
        xaxis_title="Month end",
        yaxis_title="Headcount",
    )
    return finalize_figure(fig, height=460, legend_right=True)


def plot_headcount_single_month_bar(
    month_row: pd.Series,
    depts: list[str],
    title: str,
    month_label: str,
) -> go.Figure:
    """Stacked bar for one month-end snapshot (same palette as running headcount)."""
    fig = go.Figure()
    for i, dep in enumerate(depts):
        col = _SERIES_COLORS[i % len(_SERIES_COLORS)]
        v = int(month_row.get(dep, 0))
        fig.add_trace(
            go.Bar(
                name=str(dep),
                x=[month_label],
                y=[v],
                marker=dict(
                    color=col,
                    line=dict(width=0, color="rgba(248,250,252,0.06)"),
                    cornerradius=3,
                ),
            )
        )
    fig.update_layout(
        title=title,
        barmode="stack",
        xaxis_title="Month",
        yaxis_title="Headcount",
        bargap=0.42,
    )
    return finalize_figure(fig, height=460, legend_right=True)


def plot_termination_reason_bars(
    counts: pd.Series,
    *,
    title: str | None = None,
    max_categories: int = 36,
    footnote: str | None = None,
) -> go.Figure:
    """Horizontal bar chart of inactive-exit counts by raw ``Terminated Reason`` (explore tab window)."""
    chart_title = title or "Termination reasons — inactive exits"
    palette = [
        "#38bdf8",
        "#818cf8",
        "#fbbf24",
        "#34d399",
        "#f472b6",
        "#a78bfa",
        "#2dd4bf",
        "#fb923c",
    ]
    if counts is None or counts.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No terminations in period",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=chart_title)
        return finalize_figure(fig, height=380)

    s = counts.astype(int).sort_values(ascending=False)
    if len(s) > max_categories:
        head = s.iloc[: max_categories - 1]
        tail_sum = int(s.iloc[max_categories - 1 :].sum())
        if tail_sum > 0:
            s = pd.concat([head, pd.Series({"Other reasons (combined)": tail_sum})])
        else:
            s = head

    # Ascending so largest bar sits closest to the title (top of category axis).
    s = s.sort_values(ascending=True)
    full_labels = [str(i) for i in s.index]

    def _short(lbl: str, lim: int = 76) -> str:
        t = lbl.strip()
        return t if len(t) <= lim else f"{t[: lim - 1]}…"

    short_labels = [_short(lb) for lb in full_labels]
    vals = [int(v) for v in s.tolist()]
    colors = [palette[i % len(palette)] for i in range(len(vals))]

    fig = go.Figure(
        go.Bar(
            x=vals,
            y=short_labels,
            orientation="h",
            hovertext=[
                f"{lab}<br>Count: {v:,}"
                for lab, v in zip(full_labels, vals)
            ],
            hoverinfo="text",
            marker=dict(
                color=colors,
                line=dict(color="rgba(148,163,184,0.38)", width=1),
            ),
            text=vals,
            textposition="outside",
            textfont=dict(color="#f8fafc", size=11),
        )
    )
    plot_h = min(860, 140 + 26 * max(len(vals), 6))
    fig.update_layout(
        title=chart_title,
        xaxis_title="Count",
        yaxis=dict(showticklabels=True, tickfont=dict(size=11)),
    )
    fig_out = finalize_figure(fig, height=int(plot_h))
    fig_out.update_layout(margin=dict(l=280, r=72, t=58, b=52))
    if footnote:
        fig_out.add_annotation(
            xref="paper",
            yref="paper",
            x=0.99,
            y=0.01,
            xanchor="right",
            yanchor="bottom",
            text=f"<b>Note</b><br>{footnote}",
            showarrow=False,
            font=dict(size=10, color="#e2e8f0", family="ui-sans-serif, system-ui, sans-serif"),
            align="right",
            bgcolor="rgba(15,23,42,0.94)",
            bordercolor="rgba(148,163,184,0.38)",
            borderwidth=1,
            borderpad=8,
        )
    return fig_out


def plot_termination_donut(counts: pd.Series, *, title: str | None = None) -> go.Figure:
    donut_title = title or "Termination reason (inactive, last 12 months)"
    donut_colors = ["#38bdf8", "#818cf8", "#fbbf24", "#34d399", "#f472b6"]
    if counts is None or counts.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No terminations in period",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=donut_title)
        return finalize_figure(fig, height=420, pie=True)

    colors = donut_colors[: len(counts)] + donut_colors * (len(counts) // len(donut_colors) + 1)
    colors = colors[: len(counts)]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=counts.index.astype(str),
                values=counts.values,
                hole=0.58,
                textinfo="label+percent",
                textfont=dict(color="#f8fafc", size=12),
                marker=dict(
                    colors=colors,
                    line=dict(color="rgba(148,163,184,0.45)", width=1.05),
                ),
            )
        ]
    )
    fig.update_layout(title=donut_title)
    return finalize_figure(fig, height=420, pie=True)


_BW_BLACK = "#000000"
_BW_GREY_CELL = "#6E6E6E"  # neutral grey — zero cells (no blue tint)
_BW_WHITE = "#FFFFFF"
_BW_TX_WHITE = "#FFFFFF"
_BW_TX_BLACK = "#000000"  # positives on white cells
_BW_HEADER = _BW_BLACK  # header band + department column (month headers & row labels)
_BW_GRID = "#252b36"  # 1px grid lines
_BW_LABEL = "#D1D5DB"  # header & row-label text
_BW_CANVAS = "#0B0E14"  # page behind table


def _dedupe_column_labels(idx: pd.Index) -> pd.Index:
    """Ensure unique strings so ``iloc[:, j]`` aligns 1:1 with header labels (duplicate labels skew Plotly styling)."""
    seen: dict[str, int] = {}
    out: list[str] = []
    for raw in idx.astype(str):
        base = raw.strip()
        if base not in seen:
            seen[base] = 0
            out.append(raw)
            continue
        seen[base] += 1
        out.append(f"{base} ({seen[base]})")
    return pd.Index(out)


def _force_bw_total_row(
    fill_cols: list[list[str]],
    font_cols: list[list[str]],
) -> None:
    """Last row = black band + pure white text on every column (index ``-1``)."""
    for ci in range(len(font_cols)):
        if not font_cols[ci]:
            continue
        fill_cols[ci][-1] = _BW_BLACK
        font_cols[ci][-1] = "#FFFFFF"


def bw_matrix_with_total(matrix: pd.DataFrame | None) -> pd.DataFrame | None:
    """Dept/type × month matrix plus a **Total** row (same trimming rules as ``plot_bw_department_month_table``)."""
    if matrix is None or matrix.empty:
        return None
    m = matrix.astype(int).copy()
    dup_total = (
        pd.Series(list(m.index), dtype=object)
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("total")
        .to_numpy()
    )
    if dup_total.any():
        m = m.iloc[~dup_total].astype(int)
    if m.empty:
        return None
    m.columns = _dedupe_column_labels(m.columns)
    out = m.copy()
    out.loc["Total"] = out.sum(axis=0)
    return out


def bw_matrix_monthly_average_from_total_row(matrix: pd.DataFrame | None) -> float | None:
    """Mean of the **Total** row cells — matches “average monthly hires” implied by the BW grid."""
    disp = bw_matrix_with_total(matrix)
    if disp is None or disp.empty:
        return None
    try:
        tot = disp.loc["Total"].astype(float)
    except KeyError:
        return None
    if len(tot) == 0:
        return None
    return float(tot.mean())


def style_bw_dataframe(df: pd.DataFrame) -> Styler:
    """BW grid: **single** header row (label column + months); neutral grey zeros; Total row black."""

    label_from_index = df.index.name
    label_col = (
        str(label_from_index).strip()
        if label_from_index is not None and str(label_from_index).strip()
        else "Department"
    )
    disp = df.copy().reset_index(names=[label_col])
    label_col = disp.columns[0]
    value_cols = list(disp.columns[1:])

    def row_colors(row: pd.Series) -> pd.Series:
        styles: list[str] = []
        dept_val = str(row[label_col]).strip()
        is_tot = dept_val.lower() == "total"
        border = "border: 1px solid #252b36;"
        for col in disp.columns:
            if col == label_col:
                if is_tot:
                    styles.append(
                        "background-color: #000000; color: #FFFFFF; font-weight: 600; "
                        f"text-align: center; {border}"
                    )
                else:
                    styles.append(
                        f"background-color: {_BW_HEADER}; color: #D1D5DB; font-weight: 600; "
                        f"text-align: left; padding-left: 0.75rem; {border}"
                    )
                continue
            try:
                v = int(row[col])
            except (TypeError, ValueError):
                v = 0
            if is_tot:
                styles.append(
                    "background-color: #000000; color: #FFFFFF; font-weight: 600; "
                    f"text-align: center; {border}"
                )
            elif v == 0:
                styles.append(
                    f"background-color: {_BW_GREY_CELL}; color: #FFFFFF; text-align: center; {border}"
                )
            else:
                styles.append(
                    f"background-color: #FFFFFF; color: #000000; text-align: center; {border}"
                )
        return pd.Series(styles, index=row.index)

    return (
        disp.style.apply(row_colors, axis=1)
        .format("{:,.0f}", subset=value_cols, na_rep="")
        .set_table_styles(
            [
                {
                    "selector": "",
                    "props": [
                        ("border-collapse", "collapse"),
                        (
                            "font-family",
                            "ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, sans-serif",
                        ),
                        ("font-size", "13px"),
                    ],
                },
                {
                    "selector": "thead th",
                    "props": [
                        ("background-color", _BW_HEADER),
                        ("color", "#D1D5DB"),
                        ("font-weight", "600"),
                        ("border", "1px solid #252b36"),
                        ("padding", "0.58rem 0.5rem"),
                        ("vertical-align", "middle"),
                    ],
                },
                {
                    "selector": "thead th:first-child",
                    "props": [
                        ("text-align", "left"),
                        ("padding-left", "0.75rem"),
                    ],
                },
                {
                    "selector": "thead th:not(:first-child)",
                    "props": [
                        ("text-align", "center"),
                    ],
                },
                {
                    "selector": "tbody td",
                    "props": [
                        ("vertical-align", "middle"),
                    ],
                },
            ]
        )
        .hide(axis="index")
    )


def finalize_bw_table_figure(fig: go.Figure, *, height: int, margin_top: int = 52) -> go.Figure:
    # Avoid plotly_dark template + omit layout.font: layout.font.color can cascade onto Table trace cells and
    # flatten Total-row numeric labels (dark text on black fills).
    fig.update_layout(
        template=None,
        dragmode=False,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=12, r=12, t=margin_top, b=14),
        height=height,
    )
    return fig


def plot_bw_department_month_table(
    matrix: pd.DataFrame,
    title: str,
    *,
    row_header: str = "Department",
    footnote: str | None = None,
) -> go.Figure:
    """High-contrast department × month grid: zeros grey / positives white; banded black header & totals."""
    if matrix is None or matrix.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data in this window",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=dict(text=title, x=0.01, xanchor="left", font=dict(color="#f8fafc", size=14)))
        return finalize_bw_table_figure(fig, height=320, margin_top=44)

    m = matrix.astype(int)
    # If the roster already has a department literally named "Total", drop it — we append a computed totals row.
    # Keeping both rows duplicates labels and shifts fonts/fills so the bottom totals read as department cells (dark text).
    dup_total = (
        pd.Series(list(m.index), dtype=object)
        .astype(str)
        .str.strip()
        .str.lower()
        .eq("total")
        .to_numpy()
    )
    if dup_total.any():
        m = m.iloc[~dup_total].astype(int)

    if m.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="No data in this window",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font=dict(size=13, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        fig.update_layout(title=dict(text=title, x=0.01, xanchor="left", font=dict(color="#f8fafc", size=14)))
        return finalize_bw_table_figure(fig, height=320, margin_top=44)

    m = m.copy()
    m.columns = _dedupe_column_labels(m.columns)

    n_rows = len(m.index)
    n_cols = len(m.columns)

    labels = [str(i) for i in m.index.tolist()] + ["Total"]
    vals_cols: list[list[str]] = [labels]

    fill_cols: list[list[str]] = [[_BW_HEADER] * (n_rows + 1)]
    font_cols: list[list[str]] = [[_BW_LABEL] * (n_rows + 1)]

    # Integer-position iteration avoids duplicate column-name edge cases that skew vals vs font fills.
    for j in range(n_cols):
        vals = m.iloc[:, j].tolist()
        tot = int(sum(vals))
        col_vals = [str(int(x)) for x in vals] + [str(tot)]
        vals_cols.append(col_vals)

        fills: list[str] = []
        fonts: list[str] = []
        for v in vals:
            if int(v) == 0:
                fills.append(_BW_GREY_CELL)
                fonts.append(_BW_TX_WHITE)
            else:
                fills.append(_BW_WHITE)
                fonts.append(_BW_TX_BLACK)
        fills.append(_BW_BLACK)
        fonts.append(_BW_TX_WHITE)
        fill_cols.append(fills)
        font_cols.append(fonts)

    _force_bw_total_row(fill_cols, font_cols)

    col_headers = [row_header] + list(m.columns)

    row_h = 28
    header_h = 38
    body_rows = n_rows + 1
    plot_h = min(820, header_h + row_h * body_rows + (44 if footnote else 28))

    nw = n_cols
    columnwidth = [0.26] + [max(0.06, 0.74 / max(nw, 1))] * nw
    n_trace_cols = len(vals_cols)
    col_align = ["left"] + ["center"] * (n_trace_cols - 1)

    fig = go.Figure(
        data=[
            go.Table(
                columnwidth=columnwidth,
                header=dict(
                    values=col_headers,
                    fill_color=_BW_HEADER,
                    font=dict(
                        color=_BW_LABEL,
                        size=13,
                        family="ui-sans-serif, system-ui, Segoe UI, sans-serif",
                    ),
                    align=col_align,
                    height=header_h,
                    line=dict(color=_BW_GRID, width=1),
                ),
                cells=dict(
                    values=vals_cols,
                    fill=dict(color=fill_cols),
                    font=dict(
                        color=font_cols,
                        size=12,
                        family="ui-sans-serif, system-ui, Segoe UI, sans-serif",
                    ),
                    align=col_align,
                    height=row_h,
                    line=dict(color=_BW_GRID, width=1),
                ),
            )
        ]
    )

    margin_top = 72 if footnote else 56
    fig.update_layout(
        title=dict(text=title, x=0.004, xanchor="left", font=dict(color="#f8fafc", size=14)),
    )
    if footnote:
        fig.add_annotation(
            text=footnote,
            xref="paper",
            yref="paper",
            x=0,
            y=1.07,
            xanchor="left",
            yanchor="bottom",
            showarrow=False,
            font=dict(size=11, color="#94a3b8", family="ui-sans-serif, system-ui"),
        )
        margin_top = 96

    fig = finalize_bw_table_figure(fig, height=plot_h, margin_top=margin_top)
    _force_bw_total_row(fill_cols, font_cols)
    # Re-apply cells after layout: reinforces Total-row whites vs layout/streamlit defaults.
    fig.update_traces(
        selector=dict(type="table"),
        cells=dict(
            values=vals_cols,
            fill=dict(color=fill_cols),
            font=dict(
                color=font_cols,
                size=12,
                family="Arial, Helvetica, ui-sans-serif, sans-serif",
            ),
            align=col_align,
            height=row_h,
            line=dict(color=_BW_BLACK, width=1),
        ),
    )
    return fig


EXPLORE_TAB_PERIOD_KEYS: tuple[str, ...] = (
    "hires",
    "departures",
    "quick_quits",
    "headcount",
    "inv_vol",
    "terminated_reason",
)


def explore_period_defaults() -> dict[str, None]:
    """Independent chart windows: ``None`` = rolling last 12 months from ``reference``."""
    return dict.fromkeys(EXPLORE_TAB_PERIOD_KEYS, None)


def explore_metric_tab_hover_parts(
    raw: pd.DataFrame,
    reference: pd.Timestamp,
) -> dict[str, tuple[str, str]]:
    """Human-readable blurbs plus a count line for the **calendar month of** ``reference``.

    Keys match Explore tab labels (Streamlit / Dash). Counts use the same month boundaries
    as ``hire_period`` / ``departure_period`` and month-end headcount rules elsewhere in this module.
    """
    ref = pd.Timestamp(reference).normalize()
    p = ref.to_period("M")
    month_end = p.to_timestamp(how="end").normalize()
    month_label = f"{MONTH_LABELS[p.month - 1]} {p.year}"

    hires_df = raw.loc[raw["Start Date"].notna()].copy()
    n_hires = int((hires_df["hire_period"] == p).sum())

    inactive = raw.loc[raw["User Status"].astype(str).str.lower() == "inactive"].copy()
    departures = inactive.loc[inactive["Departure Date"].notna()].copy()
    n_dep = int((departures["departure_period"] == p).sum())

    qq_df = inactive.loc[
        (inactive["Quick Quits"].astype(str).str.upper() == "YES")
        & inactive["Departure Date"].notna()
    ].copy()
    n_qq = int((qq_df["departure_period"] == p).sum())

    roster_mask = raw["Start Date"].notna() & (raw["Start Date"] <= month_end) & (
        raw["Departure Date"].isna() | (raw["Departure Date"] > month_end)
    )
    n_hc = int(roster_mask.sum())

    dep_m = departures.loc[departures["departure_period"] == p].copy()
    if dep_m.empty:
        n_inv = n_vol = n_other = 0
    else:
        buckets = dep_m["Terminated Reason"].map(classify_exit_type)
        n_inv = int(buckets.eq("Involuntary").sum())
        n_vol = int(buckets.eq("Voluntary").sum())
        n_other = int(buckets.eq("Other").sum())

    fh = format_count_display(n_hires)
    fd = format_count_display(n_dep)
    fq = format_count_display(n_qq)
    fhc = format_count_display(n_hc)
    fi = format_count_display(n_inv)
    fv = format_count_display(n_vol)
    fo = format_count_display(n_other)

    return {
        "New hires": (
            "Employees whose Start Date falls in this calendar month (same basis as the hire grids).",
            f"{month_label}: {fh} new hire(s).",
        ),
        "Departures": (
            "Inactive employees with a Departure Date in this month (all exits before optional splits).",
            f"{month_label}: {fd} departure(s).",
        ),
        "Quick quits": (
            "Subset of departures where Quick Quits is flagged YES; counted by departure month.",
            f"{month_label}: {fq} quick quit(s).",
        ),
        "Headcount": (
            "Active roster at calendar month-end: hired on or before that date and still employed "
            "(no departure on or before month-end).",
            f"{month_label} month-end: {fhc} employee(s) on roster.",
        ),
        "Involuntary vs voluntary": (
            "Departures in this month bucketed by Terminated Reason via classify_exit_type "
            "(keywords plus optional (V)/(I) suffixes).",
            f"{month_label}: {fd} exit(s) total — Involuntary {fi}, Voluntary {fv}, Other {fo}.",
        ),
        "Terminated reason": (
            "Inactive exits this month tallied by raw Terminated Reason for bars and Reason × month grids.",
            f"{month_label}: {fd} exit(s) in scope.",
        ),
    }


def explore_new_hires_narrative_markdown(
    raw: pd.DataFrame,
    reference: pd.Timestamp,
    periods_hires: pd.Period | None,
    *,
    hire_matrix: pd.DataFrame | None,
) -> str:
    """Deck-style Target / Actual / Outcome copy for the New hires Explore tab.

    **Target** is the arithmetic mean of the department × month grid **Total** row (same totals shown in UI).
    """
    actual, month_label = new_hires_actual_for_explore_window(
        raw, periods_hires, reference
    )
    tgt_mean = bw_matrix_monthly_average_from_total_row(hire_matrix)

    def _fmt_tgt(x: float) -> str:
        xr = round(x, 1)
        if abs(xr - round(xr)) < 1e-6:
            return f"{int(round(xr)):,}"
        return f"{xr:.1f}"

    lines = [
        "##### # of new hires per month",
        "",
    ]

    if tgt_mean is None:
        lines.extend(
            [
                f"**Actual ({month_label}):** {actual}",
                "",
                "**Outcome**",
                "",
                f"In **{month_label}**, the team recorded **{actual}** new hires. "
                "No monthly target is shown until the hire grid above has data.",
            ]
        )
        return "\n".join(lines)

    tgt_s = _fmt_tgt(tgt_mean)
    lines.extend(
        [
            f"**Target:** {tgt_s} · **Actual:** {actual}",
            "",
            "**Outcome**",
            "",
        ]
    )

    if tgt_mean <= 0:
        lines.append(
            f"In **{month_label}**, the team recorded **{actual}** new hires. "
            "The grid average target rounded to zero; treat comparisons cautiously."
        )
    elif actual == 0:
        lines.append(
            f"In **{month_label}**, there were **no** recorded starts. "
            f"Against a grid-average monthly benchmark of **{tgt_s}**, that signals a hiring gap worth reviewing "
            "(pipeline volume, approvals, and recruiter capacity)."
        )
    elif float(actual) > tgt_mean:
        lines.append(
            f"In **{month_label}**, the team delivered **{actual}** hires, above the grid-average target "
            f"of **{tgt_s}**. "
            "That usually reflects healthy offer-to-hire execution with limited friction closing candidates. "
            "Sustaining this pace depends on keeping offer volume and recruiter throughput steady."
        )
    elif abs(float(actual) - tgt_mean) <= 0.5:
        lines.append(
            f"In **{month_label}**, the team landed **{actual}** hires, aligned with the grid-average target "
            f"of **{tgt_s}**. "
            "Execution looks balanced versus recent monthly totals; watch pipeline aging and open reqs "
            "to hold the line."
        )
    else:
        lines.append(
            f"In **{month_label}**, the team recorded **{actual}** hires versus a grid-average benchmark "
            f"of **{tgt_s}**. "
            "That points to a shortfall versus recent monthly totals—investigate funnel conversion, "
            "time-to-offer, and competing priorities before concluding capacity limits."
        )

    return "\n".join(lines)


def new_hires_actual_for_explore_window(
    raw: pd.DataFrame,
    periods_hires: pd.Period | None,
    reference: pd.Timestamp,
) -> tuple[int, str]:
    """Return hire count and label for the narrative (single picked month vs sidebar reference month)."""
    _, _, sh, hp_h = _explore_tab_window(periods_hires, reference)
    if sh and hp_h is not None:
        p = hp_h
    else:
        p = pd.Timestamp(reference).normalize().to_period("M")
    hires_df = raw.loc[raw["Start Date"].notna()].copy()
    actual = int((hires_df["hire_period"] == p).sum())
    label = f"{MONTH_LABELS[p.month - 1]} {p.year}"
    return actual, label


def departures_actual_for_explore_window(
    raw: pd.DataFrame,
    periods_departures: pd.Period | None,
    reference: pd.Timestamp,
) -> tuple[int, str]:
    """Inactive exits with a departure date in the narrative month (matches Explore departures grid logic)."""
    _, _, sd, hp_d = _explore_tab_window(periods_departures, reference)
    if sd and hp_d is not None:
        p = hp_d
    else:
        p = pd.Timestamp(reference).normalize().to_period("M")
    inactive = raw.loc[raw["User Status"].astype(str).str.lower() == "inactive"].copy()
    departures = inactive.loc[inactive["Departure Date"].notna()].copy()
    actual = int((departures["departure_period"] == p).sum())
    label = f"{MONTH_LABELS[p.month - 1]} {p.year}"
    return actual, label


def explore_departures_narrative_markdown(
    raw: pd.DataFrame,
    reference: pd.Timestamp,
    periods_departures: pd.Period | None,
    *,
    departure_matrix: pd.DataFrame | None,
) -> str:
    """Deck-style Target / Actual / Outcome for the Departures Explore tab (grid Total-row average target)."""
    actual, month_label = departures_actual_for_explore_window(
        raw, periods_departures, reference
    )
    tgt_mean = bw_matrix_monthly_average_from_total_row(departure_matrix)

    def _fmt_tgt(x: float) -> str:
        xr = round(x, 1)
        if abs(xr - round(xr)) < 1e-6:
            return f"{int(round(xr)):,}"
        return f"{xr:.1f}"

    lines = [
        "##### # of departures per month",
        "",
    ]

    if tgt_mean is None:
        lines.extend(
            [
                f"**Actual ({month_label}):** {actual}",
                "",
                "**Outcome**",
                "",
                f"In **{month_label}**, there were **{actual}** departures in scope. "
                "No monthly benchmark is shown until the departures grid above has data.",
            ]
        )
        return "\n".join(lines)

    tgt_s = _fmt_tgt(tgt_mean)
    lines.extend(
        [
            f"**Target:** {tgt_s} · **Actual:** {actual}",
            "",
            "**Outcome**",
            "",
        ]
    )

    if tgt_mean <= 0:
        lines.append(
            f"In **{month_label}**, **{actual}** departures were recorded. "
            "The grid-average benchmark rounded to zero; interpret comparisons cautiously."
        )
    elif actual == 0:
        lines.append(
            f"In **{month_label}**, there were **no** recorded departures in scope against a benchmark of **{tgt_s}**. "
            "Confirm payroll / inactive timing before interpreting as zero attrition."
        )
    elif float(actual) > tgt_mean + 0.5:
        lines.append(
            f"In **{month_label}**, **{actual}** departures exceeded the grid-average benchmark (**{tgt_s}**). "
            "That suggests elevated exit volume versus recent months—investigate drivers (involuntary spikes, "
            "voluntary clusters, data timing) and whether replacement hiring will keep pace."
        )
    elif abs(float(actual) - tgt_mean) <= 0.5:
        lines.append(
            f"Departures were aligned with the target at **{actual}**, remaining within the expected threshold "
            "and not materially impacting net headcount growth. The overall system remains stable, with attrition "
            "at manageable levels and no immediate pressure on replacement hiring or future growth capacity."
        )
    else:
        lines.append(
            f"In **{month_label}**, **{actual}** departures fell below the grid-average benchmark (**{tgt_s}**). "
            "That often supports net headcount stability; validate whether exits are deferred versus genuinely "
            "lower turnover."
        )

    return "\n".join(lines)


def quick_quits_actual_for_explore_window(
    raw: pd.DataFrame,
    periods_quick_quits: pd.Period | None,
    reference: pd.Timestamp,
) -> tuple[int, str, int, int, int]:
    """Quick-quit counts in the narrative month + voluntary / involuntary / other via ``classify_exit_type``."""
    _, _, sq, hp_q = _explore_tab_window(periods_quick_quits, reference)
    if sq and hp_q is not None:
        p = hp_q
    else:
        p = pd.Timestamp(reference).normalize().to_period("M")
    inactive = raw.loc[raw["User Status"].astype(str).str.lower() == "inactive"].copy()
    qq = inactive[
        (inactive["Quick Quits"].astype(str).str.upper() == "YES")
        & inactive["Departure Date"].notna()
    ].copy()
    sub = qq.loc[qq["departure_period"] == p]
    actual = int(len(sub))
    if sub.empty:
        return actual, f"{MONTH_LABELS[p.month - 1]} {p.year}", 0, 0, 0
    buckets = sub["Terminated Reason"].map(classify_exit_type)
    n_inv = int(buckets.eq("Involuntary").sum())
    n_vol = int(buckets.eq("Voluntary").sum())
    n_other = int(buckets.eq("Other").sum())
    label = f"{MONTH_LABELS[p.month - 1]} {p.year}"
    return actual, label, n_inv, n_vol, n_other


def explore_quick_quits_narrative_markdown(
    raw: pd.DataFrame,
    reference: pd.Timestamp,
    periods_quick_quits: pd.Period | None,
) -> str:
    """Deck-style narrative for Quick quits; **Target** is fixed at **0** (goal = no quick quits)."""
    actual, month_label, n_inv, n_vol, n_other = quick_quits_actual_for_explore_window(
        raw, periods_quick_quits, reference
    )

    lines = [
        "##### # of quick quits per month",
        "",
        f"**Target:** 0 · **Actual:** {actual}",
        "",
        "**Outcome**",
        "",
    ]

    if actual == 0:
        lines.append(
            "No quick-quit departures were observed in "
            f"**{month_label}**, matching the target of **0**. "
            "Early-tenure exit volume is absent at this snapshot; onboarding and initial alignment appear "
            "effective, with no immediate indicators of systemic risk. Ongoing monitoring will help ensure "
            "early-tenure experience and retention remain strong."
        )
        return "\n".join(lines)

    suffix = ""
    if n_other > 0:
        suffix = f", plus **{n_other}** classified as other/unclassified"
    lines.append(
        "A small number of early-tenure departures were observed "
        f"(**{actual}** total, including **{n_vol}** voluntary and **{n_inv}** involuntary{suffix}), "
        "while overall early attrition levels remain manageable. This suggests onboarding and initial alignment "
        "continue to be broadly effective, with no immediate indicators of systemic risk. Ongoing monitoring "
        "will help ensure early-tenure experience and retention remain strong."
    )
    return "\n".join(lines)


def headcount_total_at_month_end(raw: pd.DataFrame, period: pd.Period) -> int | None:
    """Active roster count at the last day of ``period`` (same basis as headcount grids)."""
    end_ts = period.to_timestamp(how="end").normalize()
    rh = running_headcount_by_department(raw, end_ts)
    if rh.empty:
        return None
    match = rh.loc[rh["month_end"] == end_ts]
    if match.empty:
        return None
    return int(match["_total"].iloc[0])


def default_recruiting_spend_pct() -> float:
    """Illustrative recruiting-spend ratio for the Headcount narrative (override with env)."""
    env = os.environ.get("BEVERAGE_RECRUITING_SPEND_PCT", "").strip()
    if not env:
        return 1.5
    try:
        return max(0.0, float(env))
    except ValueError:
        return 1.5


def explore_headcount_narrative_markdown(
    raw: pd.DataFrame,
    reference: pd.Timestamp,
    periods_headcount: pd.Period | None,
) -> str:
    """Month-over-month active headcount story + recruiting-spend benchmark line."""
    _, _, s_hc, hp_hc = _explore_tab_window(periods_headcount, reference)
    if s_hc and hp_hc is not None:
        cur_p = hp_hc
    else:
        cur_p = pd.Timestamp(reference).normalize().to_period("M")

    cur_hc = headcount_total_at_month_end(raw, cur_p)
    prev_hc = headcount_total_at_month_end(raw, cur_p - 1)

    month_word = MONTH_LABELS[cur_p.month - 1]
    yr = int(cur_p.year)
    month_phrase = f"{month_word} {yr}"
    spend_pct = default_recruiting_spend_pct()

    lines = [
        "##### Headcount",
        "",
    ]

    if cur_hc is None:
        lines.extend(
            [
                "**—**",
                "",
                "**Outcome**",
                "",
                "Headcount could not be computed for this month-end (no usable roster history).",
            ]
        )
        return "\n".join(lines)

    lines.append(f"**{cur_hc:,}**")
    lines.extend(["", "**Outcome**", ""])

    recruit_line = (
        f"Recruiting spend = **{spend_pct:.1f}%** of payroll = efficient; "
        "world-class organizations stay under **2%**."
    )

    if prev_hc is None:
        lines.append(
            f"Active roster at **{month_phrase}** month-end stood at **{cur_hc:,}**. "
            "A prior-month comparison isn’t available before the earliest hire month in this dataset."
        )
        lines.extend(["", recruit_line])
        return "\n".join(lines)

    net = cur_hc - prev_hc
    if net > 0:
        lines.append(
            f"Headcount increased from **{prev_hc:,}** to **{cur_hc:,}** in **{month_phrase}**, "
            f"a net gain of **{net:,}** employees. "
            "This growth reflects effective hiring conversion during a seasonally constrained period and confirms "
            "that improved hiring efficiency translated directly into increased operational capacity."
        )
    elif net < 0:
        lines.append(
            f"Headcount decreased from **{prev_hc:,}** to **{cur_hc:,}** in **{month_phrase}**, "
            f"a net reduction of **{-net:,}** employees. "
            "Review hiring pace, exit drivers, and roster timing against plan to interpret whether this reflects "
            "expected reshaping or emerging attrition pressure."
        )
    else:
        lines.append(
            f"Headcount held steady at **{cur_hc:,}** in **{month_phrase}** versus **{prev_hc:,}** at the prior "
            "month-end—a net change of **0**. Stability suggests balanced inflows and outflows; continue aligning "
            "capacity plans with demand."
        )

    lines.extend(["", recruit_line])
    return "\n".join(lines)


def _explore_tab_window(
    period_opt: pd.Period | None,
    reference: pd.Timestamp,
) -> tuple[pd.PeriodIndex, pd.Timestamp, bool, pd.Period | None]:
    """``valid_months``, end date for headcount series, single-month flag, period."""
    if period_opt is None:
        return last_n_month_periods(reference, 12), reference, False, None
    hp = pd.Period(period_opt, freq="M")
    return (
        pd.PeriodIndex([hp], freq="M"),
        hp.to_timestamp(how="end").normalize(),
        True,
        hp,
    )


def _yoy_years_for_tab(
    reference: pd.Timestamp,
    single: bool,
    hp: pd.Period | None,
) -> tuple[int, int]:
    if single and hp is not None:
        return hp.year - 1, hp.year
    return reference.year - 1, reference.year


def _stack_scope_label(single: bool, hp: pd.Period | None, vm: pd.PeriodIndex) -> str:
    if single and hp is not None:
        return period_column_labels(vm)[0]
    return "last 12 months"


def _bw_scope_label(single: bool, hp: pd.Period | None, vm: pd.PeriodIndex) -> str:
    if single and hp is not None:
        return period_column_labels(vm)[0]
    return "rolling last 12 months"


def _rolling_yoy_forecast_kwargs(reference: pd.Timestamp, y2: int) -> dict[str, object]:
    """Kwargs for ``plot_yoy_outlook_figure`` (and legacy embed on ``plot_yoy_lines`` when enabled)."""
    ref = pd.Timestamp(reference).normalize()
    # December: no forward months left in calendar year. January–November: OK (Jan uses flat carry-forward).
    if int(y2) != int(ref.year) or ref.month >= 12:
        return {}
    return {
        "trend_forecast_for_year": int(y2),
        "trend_forecast_last_month": int(ref.month),
    }


def build_dashboard_figures(
    raw: pd.DataFrame,
    reference: pd.Timestamp,
    *,
    periods: Mapping[str, pd.Period | None] | None = None,
    kpis_as_of: pd.Timestamp | None = None,
) -> tuple[
    dict[str, float | int],
    tuple[go.Figure, ...],
    tuple[pd.DataFrame, ...],
    tuple[go.Figure | None, go.Figure | None, go.Figure | None, go.Figure | None],
]:
    """Snapshot KPIs use ``reference``, unless ``kpis_as_of`` is set (historic roster month-end).

    Figures continue to use ``reference`` and ``periods`` for Explore tabs.

    The fourth tuple holds optional **YoY trend outlook** figures (hires, departures, quick quits,
    headcount); ``None`` when single-month mode or outlook is not applicable.
    """
    if kpis_as_of is not None:
        kpis = snapshot_metrics_as_of(raw, kpis_as_of)
    else:
        kpis = snapshot_metrics(raw, reference)

    reference = pd.Timestamp(reference).normalize()
    merged = explore_period_defaults()
    if periods is not None:
        merged.update(periods)
    periods = merged

    hires = raw[raw["Start Date"].notna()].copy()
    inactive = raw[raw["User Status"].astype(str).str.lower() == "inactive"].copy()
    departures = inactive[inactive["Departure Date"].notna()].copy()
    quick_quits = inactive[
        (inactive["Quick Quits"].astype(str).str.upper() == "YES")
        & inactive["Departure Date"].notna()
    ].copy()

    roster_depts = pd.Index(sorted(raw["Department"].astype(str).unique()))

    # --- New hires tab ---
    vm_h, _, sh, hp_h = _explore_tab_window(periods["hires"], reference)
    y1h, y2h = _yoy_years_for_tab(reference, sh, hp_h)
    yoy_h = yoy_monthly_counts(
        hires, "Start Date", (y1h, y2h), clip_future_months_as_of=reference
    )
    lb_h = _bw_scope_label(sh, hp_h, vm_h)
    if sh:
        outlook_hires = None
        fig_yoy_h = plot_yoy_same_month_bars(
            yoy_h,
            hp_h.month,
            f"YoY hires — {lb_h}: {y1h} vs {y2h}",
            "Hires",
        )
    else:
        fc_kw_h = _rolling_yoy_forecast_kwargs(reference, y2h)
        fig_yoy_h = plot_yoy_lines(
            yoy_h,
            f"YoY hires — {y1h} vs {y2h}",
            "Hires",
            embed_trend_forecast=False,
        )
        outlook_hires = (
            plot_yoy_outlook_figure(
                yoy_h,
                title=f"Trend outlook — hires ({y2h})",
                y_label="Hires",
                **fc_kw_h,
            )
            if fc_kw_h
            else None
        )
    hire_mat = department_month_matrix_full_roster(
        hires, "hire_period", vm_h, roster_depts
    )

    # --- Departures tab ---
    vm_d, _, sd, hp_d = _explore_tab_window(periods["departures"], reference)
    y1d, y2d = _yoy_years_for_tab(reference, sd, hp_d)
    yoy_d = yoy_monthly_counts(
        departures, "Departure Date", (y1d, y2d), clip_future_months_as_of=reference
    )
    lb_d = _bw_scope_label(sd, hp_d, vm_d)
    if sd:
        outlook_dep = None
        fig_yoy_d = plot_yoy_same_month_bars(
            yoy_d,
            hp_d.month,
            f"YoY departures — {lb_d}: {y1d} vs {y2d}",
            "Departures",
        )
    else:
        fc_kw_d = _rolling_yoy_forecast_kwargs(reference, y2d)
        fig_yoy_d = plot_yoy_lines(
            yoy_d,
            f"YoY departures — {y1d} vs {y2d}",
            "Departures",
            embed_trend_forecast=False,
        )
        outlook_dep = (
            plot_yoy_outlook_figure(
                yoy_d,
                title=f"Trend outlook — departures ({y2d})",
                y_label="Departures",
                **fc_kw_d,
            )
            if fc_kw_d
            else None
        )
    dep_mat = department_month_matrix_full_roster(
        departures, "departure_period", vm_d, roster_depts
    )

    # --- Quick quits tab ---
    vm_q, _, sq, hp_q = _explore_tab_window(periods["quick_quits"], reference)
    y1q, y2q = _yoy_years_for_tab(reference, sq, hp_q)
    yoy_q = yoy_monthly_counts(
        quick_quits, "Departure Date", (y1q, y2q), clip_future_months_as_of=reference
    )
    lb_q = _bw_scope_label(sq, hp_q, vm_q)
    if sq:
        outlook_qq = None
        fig_yoy_q = plot_yoy_same_month_bars(
            yoy_q,
            hp_q.month,
            f"YoY quick quits — {lb_q}: {y1q} vs {y2q}",
            "Quick quits",
        )
    else:
        fc_kw_q = _rolling_yoy_forecast_kwargs(reference, y2q)
        fig_yoy_q = plot_yoy_lines(
            yoy_q,
            f"YoY quick quits — {y1q} vs {y2q}",
            "Quick quits",
            embed_trend_forecast=False,
        )
        outlook_qq = (
            plot_yoy_outlook_figure(
                yoy_q,
                title=f"Trend outlook — quick quits ({y2q})",
                y_label="Quick quits",
                **fc_kw_q,
            )
            if fc_kw_q
            else None
        )
    qq_mat = department_month_matrix_full_roster(
        quick_quits, "departure_period", vm_q, roster_depts
    )

    # --- Headcount tab ---
    vm_hc, rh_end_hc, s_hc, hp_hc = _explore_tab_window(
        periods["headcount"], reference
    )
    rh_hc = running_headcount_by_department(raw, rh_end_hc)
    lb_hc = _bw_scope_label(s_hc, hp_hc, vm_hc)

    y1hc, y2hc = _yoy_years_for_tab(reference, s_hc, hp_hc)
    hc_yoy_totals = total_headcount_yoy_monthly(
        raw, (y1hc, y2hc), clip_future_months_as_of=reference
    )
    if s_hc:
        outlook_hc = None
        assert hp_hc is not None
        fig_hc_yoy = plot_yoy_same_month_bars(
            hc_yoy_totals,
            hp_hc.month,
            f"YoY total headcount (month-end) — {lb_hc}: {y1hc} vs {y2hc}",
            "Total headcount",
        )
    else:
        fc_kw_hc = _rolling_yoy_forecast_kwargs(reference, y2hc)
        fig_hc_yoy = plot_yoy_lines(
            hc_yoy_totals,
            f"YoY total headcount (month-end) — {y1hc} vs {y2hc}",
            "Total headcount",
            embed_trend_forecast=False,
        )
        outlook_hc = (
            plot_yoy_outlook_figure(
                hc_yoy_totals,
                title=f"Trend outlook — total headcount ({y2hc})",
                y_label="Total headcount",
                **fc_kw_hc,
            )
            if fc_kw_hc
            else None
        )

    hc_mat = headcount_department_month_matrix(rh_hc, vm_hc)
    if not hc_mat.empty:
        hc_mat = hc_mat.reindex(roster_depts, fill_value=0).astype(int)
        hc_mat.index.name = "Department"

    hc_bw_title = (
        f"Headcount (active, month-end) — department × month ({period_column_labels(vm_hc)[0]})"
        if s_hc and hp_hc is not None
        else "Headcount (active, month-end) — department × month"
    )

    # --- Involuntary vs voluntary tab (shared window for exit type + dept grids) ---
    vm_iv, _, s_iv, hp_iv = _explore_tab_window(periods["inv_vol"], reference)
    lb_iv = _bw_scope_label(s_iv, hp_iv, vm_iv)
    exit_mat = exit_type_month_matrix(departures, vm_iv)
    fig_exit_iv = plot_exit_type_month_lines(
        exit_mat,
        f"Exit type × month — Involuntary vs Voluntary ({lb_iv})",
    )
    inv_sub = departures_for_exit_class(departures, "Involuntary")
    vol_sub = departures_for_exit_class(departures, "Voluntary")
    inv_dept_mat = department_month_matrix_full_roster(
        inv_sub, "departure_period", vm_iv, roster_depts
    )
    vol_dept_mat = department_month_matrix_full_roster(
        vol_sub, "departure_period", vm_iv, roster_depts
    )

    # --- Terminated reason tab ---
    vm_tr, _, s_tr, hp_tr = _explore_tab_window(
        periods["terminated_reason"], reference
    )
    lb_tr = _bw_scope_label(s_tr, hp_tr, vm_tr)
    _reason_labels = sorted(raw["Terminated Reason"].astype(str).unique())
    roster_reasons = pd.Index(
        [r for r in _reason_labels if str(r).strip().lower() != "(unknown)"]
    )
    term_sub = departures[
        filter_period_in_range(departures["departure_period"], vm_tr)
    ]
    term_counts = term_sub["Terminated Reason"].value_counts().sort_values(
        ascending=False
    )
    term_reason_mat = termination_reason_month_matrix(
        departures, vm_tr, roster_reasons
    )
    term_chart_title = f"Termination reasons — inactive exits ({lb_tr})"
    term_note = None
    if not s_tr and len(vm_tr) >= 3:
        term_note = (
            "Reason mix for exits in this period — descriptive only; not a prediction of future reasons."
        )
    fig_term_bar = plot_termination_reason_bars(
        term_counts, title=term_chart_title, footnote=term_note
    )
    figs = (
        fig_yoy_h,
        fig_yoy_d,
        fig_yoy_q,
        fig_hc_yoy,
        fig_exit_iv,
        fig_term_bar,
        plot_bw_department_month_table(
            hire_mat,
            f"New hires — department × month ({lb_h})",
        ),
        plot_bw_department_month_table(
            dep_mat,
            f"Departures — department × month ({lb_d})",
        ),
        plot_bw_department_month_table(
            qq_mat,
            f"Quick quits — department × month ({lb_q})",
        ),
        plot_bw_department_month_table(hc_mat, hc_bw_title),
        plot_bw_department_month_table(
            exit_mat,
            f"Involuntary vs voluntary exits — month ({lb_iv})",
            row_header="Type",
            footnote=(
                "Buckets inferred from Terminated Reason text (see analytics.classify_exit_type)."
            ),
        ),
        plot_bw_department_month_table(
            inv_dept_mat,
            f"Involuntary exits — department × month ({lb_iv})",
            footnote=(
                "Inactive exits classified Involuntary via analytics.classify_exit_type "
                "(Terminated Reason keywords)."
            ),
        ),
        plot_bw_department_month_table(
            vol_dept_mat,
            f"Voluntary exits — department × month ({lb_iv})",
            footnote=(
                "Inactive exits classified Voluntary via analytics.classify_exit_type "
                "(Terminated Reason keywords)."
            ),
        ),
        plot_bw_department_month_table(
            term_reason_mat,
            f"Terminated Reason × month — inactive exits ({lb_tr})",
            row_header="Terminated Reason",
            footnote=(
                "Counts by raw Terminated Reason; ``(Unknown)`` omitted; zeros where none in window."
            ),
        ),
    )
    bw_matrices = (
        hire_mat,
        dep_mat,
        qq_mat,
        hc_mat,
        exit_mat,
        inv_dept_mat,
        vol_dept_mat,
        term_reason_mat,
    )
    outlook_figs = (outlook_hires, outlook_dep, outlook_qq, outlook_hc)
    return kpis, figs, bw_matrices, outlook_figs
