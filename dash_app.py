"""
Beverage Factory — Plotly Dash + Bootstrap UI (alternative to Streamlit).

Run: python dash_app.py
  or: dash run dash_app.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, dcc, html
from dash.exceptions import PreventUpdate

import analytics

PATH = analytics.resolve_data_path()


def _dash_outlook_figure(fig: object | None) -> object:
    """Dash always needs a figure; Streamlit hides outlook when ``None``."""
    return fig if fig is not None else analytics.blank_yoy_outlook_figure()


def _dash_year_options(raw: pd.DataFrame, ref: pd.Timestamp) -> list[int]:
    dmin = raw["Start Date"].min()
    dmx = pd.concat([raw["Start Date"], raw["Departure Date"]], ignore_index=True).max()
    min_y = int(dmin.year) if pd.notna(dmin) else ref.year - 3
    max_y = int(max(ref.year, pd.Timestamp(dmx).year)) if pd.notna(dmx) else ref.year
    ys = list(range(min_y, max_y + 1))
    return ys if ys else [ref.year]


def _explore_period_controls(tab_key: str, raw: pd.DataFrame, ref: pd.Timestamp) -> dbc.Card:
    """Rolling L12M vs single month — independent per Explore tab (matches Streamlit)."""
    ys = _dash_year_options(raw, ref)
    y_val = ref.year if ref.year in ys else ys[-1]
    return dbc.Card(
        [
            dbc.CardBody(
                [
                    html.Label(
                        "Time window for this tab",
                        className="form-label fw-semibold small mb-2",
                    ),
                    dcc.RadioItems(
                        id=f"explore-{tab_key}-mode",
                        options=[
                            {"label": " Rolling last 12 months", "value": "rolling"},
                            {"label": " Single calendar month", "value": "single"},
                        ],
                        value="rolling",
                        labelStyle={"display": "inline-block", "margin-right": "1rem"},
                        inputStyle={"margin-right": "0.35rem"},
                        className="neo-sub mb-2",
                    ),
                    dbc.Row(
                        [
                            dbc.Col(
                                [
                                    html.Label(
                                        "Year",
                                        className="form-label fw-semibold small",
                                    ),
                                    dcc.Dropdown(
                                        id=f"explore-{tab_key}-year",
                                        options=[
                                            {"label": str(y), "value": y} for y in ys
                                        ],
                                        value=y_val,
                                        clearable=False,
                                    ),
                                ],
                                md=6,
                            ),
                            dbc.Col(
                                [
                                    html.Label(
                                        "Month",
                                        className="form-label fw-semibold small",
                                    ),
                                    dcc.Dropdown(
                                        id=f"explore-{tab_key}-month",
                                        options=[
                                            {
                                                "label": analytics.MONTH_LABELS[i],
                                                "value": i + 1,
                                            }
                                            for i in range(12)
                                        ],
                                        value=ref.month,
                                        clearable=False,
                                    ),
                                ],
                                md=6,
                            ),
                        ],
                        className="g-2",
                    ),
                ]
            ),
        ],
        className="mb-3 neo-card",
    )


def _period_from_explore(
    mode: str | None,
    year: int | None,
    month: int | None,
) -> pd.Period | None:
    if mode != "single":
        return None
    if year is None or month is None:
        return None
    return pd.Period(f"{int(year)}-{int(month):02d}", freq="M")


_PATH_DIR = Path(__file__).resolve().parent

app = dash.Dash(
    __name__,
    assets_folder=str(_PATH_DIR / "assets"),
    external_stylesheets=[dbc.themes.CYBORG, dbc.icons.BOOTSTRAP],
    suppress_callback_exceptions=True,
)
app.title = "HR Ops / HRBPs Dashboard"


def layout_error(msg: str) -> dbc.Container:
    return dbc.Container(
        [
            html.H2("HR Ops / HRBPs Dashboard", className="neo-h1 pb-3"),
            dbc.Alert(msg, color="danger", className="neo-card"),
        ],
        className="py-4",
        fluid=True,
    )


def _kpi_col(label: str, e_id: str, value: str, *, xl: int = 3) -> dbc.Col:
    return dbc.Col(
        html.Div(
            [
                html.Div(label, className="neo-sub mb-1"),
                html.Div(id=e_id, className="neo-kpi-value", children=value),
            ],
            className="neo-kpi h-100 mb-2",
            style={"minHeight": "5.75rem"},
        ),
        xs=12,
        sm=6,
        xl=xl,
    )


def _dash_explore_tip(blurb: str, metric: str) -> html.Div:
    return html.Div(
        [
            html.P(blurb, className="small text-secondary mb-2"),
            html.P(metric, className="small fw-semibold mb-0"),
        ],
        style={"maxWidth": "300px", "textAlign": "left"},
    )


def layout_main(raw: pd.DataFrame, path_name: str) -> dbc.Container:
    default_dt = pd.Timestamp.today().normalize()
    kpis, figs, _bw_mats, outlook_figs = analytics.build_dashboard_figures(raw, default_dt)
    (
        f_hi_y,
        f_dep_y,
        f_qq_y,
        f_hc_yoy,
        f_exit_iv,
        f_term,
        tbl_hires,
        tbl_dep,
        tbl_qq,
        tbl_hc_m,
        tbl_exit,
        tbl_inv_dept,
        tbl_vol_dept,
        tbl_term_reason,
    ) = figs
    oh, od, oq, ohc = outlook_figs
    gcfg = {
        "responsive": True,
        "displayModeBar": True,
        "displaylogo": False,
        "scrollZoom": False,
        "toImageButtonOptions": {"filename": "chart"},
    }

    _tip0 = analytics.explore_metric_tab_hover_parts(raw, default_dt)

    return dbc.Container(
        [
            html.Header(
                [
                    html.H1("HR Ops / HRBPs Dashboard", className="neo-h1"),
                    html.P(
                        f"{path_name} · {len(raw):,} rows · same metrics as the Streamlit app",
                        className="neo-sub mb-0",
                    ),
                ],
                className="pb-3 mb-4",
            ),
            dbc.Card(
                [
                    dbc.CardHeader(html.Span("Reference & KPI", className="fw-semibold")),
                    dbc.CardBody(
                        [
                            html.Label(
                                "Reference date",
                                className="form-label fw-semibold",
                            ),
                            dcc.DatePickerSingle(
                                id="reference-date",
                                date=default_dt.date(),
                                display_format="YYYY-MM-DD",
                            ),
                            html.Small(
                                "Explore charts use the reference date for rolling windows. Snapshot KPIs "
                                "use that reference unless Historic KPI snapshot is enabled below.",
                                className="d-block neo-sub mt-1 mb-2",
                            ),
                            html.Label(
                                "Historic KPI snapshot",
                                className="form-label fw-semibold mt-2 mb-1",
                            ),
                            dbc.Switch(
                                id="historic-kpi-switch",
                                label="As-of calendar month (reconstructed roster)",
                                value=False,
                                className="mb-2",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "KPI year",
                                                className="form-label fw-semibold small",
                                            ),
                                            dcc.Dropdown(
                                                id="historic-kpi-year",
                                                options=[
                                                    {"label": str(y), "value": y}
                                                    for y in _dash_year_options(raw, default_dt)
                                                ],
                                                value=default_dt.year,
                                                clearable=False,
                                            ),
                                        ],
                                        md=6,
                                    ),
                                    dbc.Col(
                                        [
                                            html.Label(
                                                "KPI month",
                                                className="form-label fw-semibold small",
                                            ),
                                            dcc.Dropdown(
                                                id="historic-kpi-month",
                                                options=[
                                                    {
                                                        "label": analytics.MONTH_LABELS[i],
                                                        "value": i + 1,
                                                    }
                                                    for i in range(12)
                                                ],
                                                value=default_dt.month,
                                                clearable=False,
                                            ),
                                        ],
                                        md=6,
                                    ),
                                ],
                                className="g-2 mb-3",
                            ),
                            dbc.Row(
                                [
                                    _kpi_col(
                                        "Avg tenure — active (years)",
                                        "kpi-tenure",
                                        analytics.format_tenure_years_display(
                                            float(kpis["tenure_years"]),
                                        ),
                                    ),
                                    _kpi_col(
                                        "Active employees",
                                        "kpi-active",
                                        analytics.format_count_display(kpis["active_count"]),
                                    ),
                                    _kpi_col(
                                        "Inactive employees",
                                        "kpi-inactive",
                                        analytics.format_count_display(kpis["inactive_count"]),
                                    ),
                                    _kpi_col(
                                        "Total on roster",
                                        "kpi-total",
                                        analytics.format_count_display(kpis["total_count"]),
                                    ),
                                ],
                                className="g-2",
                            ),
                            dbc.Row(
                                [
                                    _kpi_col(
                                        "Hires (L12M)",
                                        "kpi-hires-l12",
                                        analytics.format_count_display(kpis["hires_last_12"]),
                                        xl=3,
                                    ),
                                    _kpi_col(
                                        "Departures (L12M)",
                                        "kpi-exits-l12",
                                        analytics.format_count_display(kpis["departures_last_12"]),
                                        xl=3,
                                    ),
                                    _kpi_col(
                                        "Quick quits (L12M)",
                                        "kpi-qq-l12",
                                        analytics.format_count_display(kpis["quick_quits_last_12"]),
                                        xl=3,
                                    ),
                                    _kpi_col(
                                        "Net hires − exits (L12M)",
                                        "kpi-net-l12",
                                        analytics.format_count_display(kpis["net_change_last_12"]),
                                        xl=3,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ]
                    ),
                ],
                className="mb-4 neo-card",
            ),
            html.H5("Explore metrics", className="neo-section-title"),
            html.Div(
                [
                    dbc.Tabs(
                        [
                            dbc.Tab(
                                tab_id="tab-hires",
                                label=html.Span(
                                    "New hires",
                                    id="explore-tab-hires",
                                    className="neo-tab-hover",
                                ),
                        children=[
                            _explore_period_controls("hires", raw, default_dt),
                            html.P(
                                "YoY comparison, department × month grid, then trend outlook when rolling.",
                                className="neo-sub mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-h-yoy",
                                            figure=f_hi_y,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-hires",
                                            figure=tbl_hires,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-h-outlook",
                                            figure=_dash_outlook_figure(oh),
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ],
                    ),
                            dbc.Tab(
                                tab_id="tab-dep",
                                label=html.Span(
                                    "Departures",
                                    id="explore-tab-dep",
                                    className="neo-tab-hover",
                                ),
                        children=[
                            _explore_period_controls("dep", raw, default_dt),
                            html.P(
                                "YoY comparison, department × month grid, then trend outlook when rolling.",
                                className="neo-sub mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-d-yoy",
                                            figure=f_dep_y,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-dep",
                                            figure=tbl_dep,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-d-outlook",
                                            figure=_dash_outlook_figure(od),
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ],
                    ),
                            dbc.Tab(
                                tab_id="tab-qq",
                                label=html.Span(
                                    "Quick quits",
                                    id="explore-tab-qq",
                                    className="neo-tab-hover",
                                ),
                        children=[
                            _explore_period_controls("qq", raw, default_dt),
                            html.P(
                                "YoY comparison, department × month grid, then trend outlook when rolling.",
                                className="neo-sub mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-q-yoy",
                                            figure=f_qq_y,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-qq",
                                            figure=tbl_qq,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-q-outlook",
                                            figure=_dash_outlook_figure(oq),
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ],
                    ),
                            dbc.Tab(
                                tab_id="tab-hc",
                                label=html.Span(
                                    "Headcount",
                                    id="explore-tab-hc",
                                    className="neo-tab-hover",
                                ),
                        children=[
                            _explore_period_controls("hc", raw, default_dt),
                            html.P(
                                "YoY total month-end headcount (matches department grid Total row), "
                                "department × month table, then trend outlook when rolling.",
                                className="neo-sub mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-hc-yoy-totals",
                                            figure=f_hc_yoy,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-hc",
                                            figure=tbl_hc_m,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-hc-outlook",
                                            figure=_dash_outlook_figure(ohc),
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-2",
                            ),
                        ],
                    ),
                            dbc.Tab(
                                tab_id="tab-exits",
                                label=html.Span(
                                    "Involuntary vs voluntary",
                                    id="explore-tab-iv",
                                    className="neo-tab-hover",
                                ),
                        children=[
                            _explore_period_controls("iv", raw, default_dt),
                            html.P(
                                "Exit type × month line chart (Involuntary vs Voluntary — numeric labels), "
                                "department × month grids, and exit-type × month summary "
                                "(aggregated buckets from analytics.classify_exit_type).",
                                className="neo-sub mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-exit-iv",
                                            figure=f_exit_iv,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-inv-dept",
                                            figure=tbl_inv_dept,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-vol-dept",
                                            figure=tbl_vol_dept,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-exits",
                                            figure=tbl_exit,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3",
                            ),
                        ],
                    ),
                            dbc.Tab(
                                tab_id="tab-term-reason",
                                label=html.Span(
                                    "Terminated reason",
                                    id="explore-tab-term",
                                    className="neo-tab-hover",
                                ),
                        children=[
                            _explore_period_controls("term", raw, default_dt),
                            html.P(
                                "Termination reason totals (horizontal bar) for inactive exits in this tab's window; "
                                "table below shows Reason × month.",
                                className="neo-sub mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-term-bar",
                                            figure=f_term,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3 mb-3",
                            ),
                            dbc.Row(
                                [
                                    dbc.Col(
                                        dcc.Graph(
                                            id="graph-tbl-term-reason",
                                            figure=tbl_term_reason,
                                            config=gcfg,
                                        ),
                                        lg=12,
                                    ),
                                ],
                                className="g-3",
                            ),
                        ],
                    ),
                ],
                        active_tab="tab-hires",
                        class_name="neo-metric-tabs",
                    ),
                    dbc.Tooltip(
                        id="explore-tip-hires",
                        target="explore-tab-hires",
                        placement="bottom",
                        delay={"show": 250, "hide": 80},
                        autohide=False,
                        children=_dash_explore_tip(*_tip0["New hires"]),
                    ),
                    dbc.Tooltip(
                        id="explore-tip-dep",
                        target="explore-tab-dep",
                        placement="bottom",
                        delay={"show": 250, "hide": 80},
                        autohide=False,
                        children=_dash_explore_tip(*_tip0["Departures"]),
                    ),
                    dbc.Tooltip(
                        id="explore-tip-qq",
                        target="explore-tab-qq",
                        placement="bottom",
                        delay={"show": 250, "hide": 80},
                        autohide=False,
                        children=_dash_explore_tip(*_tip0["Quick quits"]),
                    ),
                    dbc.Tooltip(
                        id="explore-tip-hc",
                        target="explore-tab-hc",
                        placement="bottom",
                        delay={"show": 250, "hide": 80},
                        autohide=False,
                        children=_dash_explore_tip(*_tip0["Headcount"]),
                    ),
                    dbc.Tooltip(
                        id="explore-tip-iv",
                        target="explore-tab-iv",
                        placement="bottom",
                        delay={"show": 250, "hide": 80},
                        autohide=False,
                        children=_dash_explore_tip(*_tip0["Involuntary vs voluntary"]),
                    ),
                    dbc.Tooltip(
                        id="explore-tip-term",
                        target="explore-tab-term",
                        placement="bottom",
                        delay={"show": 250, "hide": 80},
                        autohide=False,
                        children=_dash_explore_tip(*_tip0["Terminated reason"]),
                    ),
                ],
            ),
        ],
        fluid=True,
        className="py-4 px-lg-4",
        style={"maxWidth": "1400px", "margin": "0 auto"},
    )


_DASH_READY = False
if PATH.exists():
    try:
        _raw = analytics.load_employees(str(PATH))
        app.layout = layout_main(_raw, PATH.name)
        _DASH_READY = True
    except Exception as e:
        app.layout = layout_error(f"Could not load Excel ({PATH}): {e}")
else:
    app.layout = layout_error(
        f"Excel not found at `{PATH}`. Copy your file beside the app or set BEVERAGE_FACTORY_XLSX."
    )


if _DASH_READY:

    @callback(
        Output("graph-h-yoy", "figure"),
        Output("graph-d-yoy", "figure"),
        Output("graph-q-yoy", "figure"),
        Output("graph-hc-yoy-totals", "figure"),
        Output("graph-exit-iv", "figure"),
        Output("graph-term-bar", "figure"),
        Output("graph-tbl-hires", "figure"),
        Output("graph-h-outlook", "figure"),
        Output("graph-tbl-dep", "figure"),
        Output("graph-d-outlook", "figure"),
        Output("graph-tbl-qq", "figure"),
        Output("graph-q-outlook", "figure"),
        Output("graph-tbl-hc", "figure"),
        Output("graph-hc-outlook", "figure"),
        Output("graph-tbl-exits", "figure"),
        Output("graph-tbl-inv-dept", "figure"),
        Output("graph-tbl-vol-dept", "figure"),
        Output("graph-tbl-term-reason", "figure"),
        Output("kpi-tenure", "children"),
        Output("kpi-active", "children"),
        Output("kpi-inactive", "children"),
        Output("kpi-total", "children"),
        Output("kpi-hires-l12", "children"),
        Output("kpi-exits-l12", "children"),
        Output("kpi-qq-l12", "children"),
        Output("kpi-net-l12", "children"),
        Output("explore-tip-hires", "children"),
        Output("explore-tip-dep", "children"),
        Output("explore-tip-qq", "children"),
        Output("explore-tip-hc", "children"),
        Output("explore-tip-iv", "children"),
        Output("explore-tip-term", "children"),
        Input("reference-date", "date"),
        Input("historic-kpi-switch", "value"),
        Input("historic-kpi-year", "value"),
        Input("historic-kpi-month", "value"),
        Input("explore-hires-mode", "value"),
        Input("explore-hires-year", "value"),
        Input("explore-hires-month", "value"),
        Input("explore-dep-mode", "value"),
        Input("explore-dep-year", "value"),
        Input("explore-dep-month", "value"),
        Input("explore-qq-mode", "value"),
        Input("explore-qq-year", "value"),
        Input("explore-qq-month", "value"),
        Input("explore-hc-mode", "value"),
        Input("explore-hc-year", "value"),
        Input("explore-hc-month", "value"),
        Input("explore-iv-mode", "value"),
        Input("explore-iv-year", "value"),
        Input("explore-iv-month", "value"),
        Input("explore-term-mode", "value"),
        Input("explore-term-year", "value"),
        Input("explore-term-month", "value"),
    )
    def refresh_charts(
        reference_date_str: str | None,
        historic_switch: bool | None,
        historic_year: int | None,
        historic_month: int | None,
        hires_mode: str | None,
        hires_year: int | None,
        hires_month: int | None,
        dep_mode: str | None,
        dep_year: int | None,
        dep_month: int | None,
        qq_mode: str | None,
        qq_year: int | None,
        qq_month: int | None,
        hc_mode: str | None,
        hc_year: int | None,
        hc_month: int | None,
        iv_mode: str | None,
        iv_year: int | None,
        iv_month: int | None,
        term_mode: str | None,
        term_year: int | None,
        term_month: int | None,
    ):
        if not reference_date_str:
            raise PreventUpdate
        raw = analytics.load_employees(str(PATH))
        reference = pd.Timestamp(reference_date_str)
        kpis_as_of = None
        try:
            _use_hist = bool(historic_switch)
            if (
                _use_hist
                and historic_year is not None
                and historic_month is not None
            ):
                kpis_as_of = analytics.month_end_timestamp(
                    int(historic_year),
                    int(historic_month),
                )
        except (TypeError, ValueError):
            kpis_as_of = None
        periods = {
            "hires": _period_from_explore(hires_mode, hires_year, hires_month),
            "departures": _period_from_explore(dep_mode, dep_year, dep_month),
            "quick_quits": _period_from_explore(qq_mode, qq_year, qq_month),
            "headcount": _period_from_explore(hc_mode, hc_year, hc_month),
            "inv_vol": _period_from_explore(iv_mode, iv_year, iv_month),
            "terminated_reason": _period_from_explore(
                term_mode, term_year, term_month
            ),
        }
        kpis, figs, _bw_mats, outlook_figs = analytics.build_dashboard_figures(
            raw, reference, periods=periods, kpis_as_of=kpis_as_of
        )
        oh, od, oq, ohc = outlook_figs
        tip_parts = analytics.explore_metric_tab_hover_parts(raw, reference)
        (
            f_hi_y,
            f_dep_y,
            f_qq_y,
            f_hc_yoy,
            f_exit_iv,
            f_term,
            tbl_hires,
            tbl_dep,
            tbl_qq,
            tbl_hc_m,
            tbl_exit,
            tbl_inv_dept,
            tbl_vol_dept,
            tbl_term_reason,
        ) = figs
        return (
            f_hi_y,
            f_dep_y,
            f_qq_y,
            f_hc_yoy,
            f_exit_iv,
            f_term,
            tbl_hires,
            _dash_outlook_figure(oh),
            tbl_dep,
            _dash_outlook_figure(od),
            tbl_qq,
            _dash_outlook_figure(oq),
            tbl_hc_m,
            _dash_outlook_figure(ohc),
            tbl_exit,
            tbl_inv_dept,
            tbl_vol_dept,
            tbl_term_reason,
            analytics.format_tenure_years_display(float(kpis["tenure_years"])),
            analytics.format_count_display(kpis["active_count"]),
            analytics.format_count_display(kpis["inactive_count"]),
            analytics.format_count_display(kpis["total_count"]),
            analytics.format_count_display(kpis["hires_last_12"]),
            analytics.format_count_display(kpis["departures_last_12"]),
            analytics.format_count_display(kpis["quick_quits_last_12"]),
            analytics.format_count_display(kpis["net_change_last_12"]),
            _dash_explore_tip(*tip_parts["New hires"]),
            _dash_explore_tip(*tip_parts["Departures"]),
            _dash_explore_tip(*tip_parts["Quick quits"]),
            _dash_explore_tip(*tip_parts["Headcount"]),
            _dash_explore_tip(*tip_parts["Involuntary vs voluntary"]),
            _dash_explore_tip(*tip_parts["Terminated reason"]),
        )


def run() -> None:
    # debug=False keeps a single process when launched from GUI / nohup scripts
    app.run(debug=False, port=8050)


if __name__ == "__main__":
    run()
