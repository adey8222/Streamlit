"""
Beverage Factory — Employee analytics (Streamlit UI; logic in analytics.py).
"""

from __future__ import annotations

import hashlib
import html
import io
import json

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from streamlit.column_config import NumberColumn, TextColumn

import analytics

_PLOT_CFG = {
    "displaylogo": False,
    "displayModeBar": True,
    # Wheel / touchpad over the chart must not zoom or steal scroll from the page.
    "scrollZoom": False,
    "toImageButtonOptions": {"filename": "chart", "scale": 2},
}


def _inject_style() -> None:
    """Layered typography, glass panels, bordered sections (paired with `.streamlit/config.toml`)."""
    st.markdown(
        """
<style>

html, body {
  scroll-behavior: smooth;
}

[data-testid="stApp"],
html, body {
  font-family: "Segoe UI Variable", "Inter", ui-sans-serif, system-ui, sans-serif !important;
  font-feature-settings: "kern" 1, "liga" 1;
  min-height: 100vh !important;
  background-color: #030508 !important;
  background-image:
    radial-gradient(ellipse 120% 90% at 10% 10%, rgba(45, 140, 195, 0.09), transparent 55%),
    radial-gradient(ellipse 110% 85% at 92% 8%, rgba(95, 85, 155, 0.075), transparent 52%),
    linear-gradient(
      115deg,
      transparent 0%,
      rgba(40, 120, 175, 0.055) 22%,
      transparent 38%,
      rgba(130, 65, 105, 0.045) 58%,
      transparent 72%,
      rgba(85, 75, 155, 0.05) 88%,
      transparent 100%
    ),
    linear-gradient(168deg, #030508 0%, #070b14 48%, #04060a 100%) !important;
  background-size: 185% 185%, 175% 175%, 450% 450%, 100% 100% !important;
  background-position: 10% 8%, 90% 12%, 0% 50%, center !important;
  background-attachment: fixed !important;
  animation: app-bg-base-shift 26s ease-in-out infinite !important;
  color-scheme: dark;
  color: #e2e8f0 !important;
}

[data-testid="stApp"] {
  position: relative !important;
  isolation: isolate !important;
}

[data-testid="stApp"]::before {
  content: "" !important;
  position: fixed !important;
  inset: -20vh -20vw !important;
  z-index: 0 !important;
  pointer-events: none !important;
  opacity: 0.38 !important;
  filter: blur(48px) saturate(1.15) !important;
  background:
    radial-gradient(ellipse 65vw 50vh at 22% 28%, rgba(38, 115, 165, 0.28), transparent 58%),
    radial-gradient(ellipse 58vw 46vh at 85% 22%, rgba(95, 82, 145, 0.22), transparent 56%),
    radial-gradient(ellipse 62vw 52vh at 72% 90%, rgba(120, 55, 95, 0.16), transparent 58%),
    radial-gradient(ellipse 48vw 44vh at 8% 82%, rgba(28, 110, 125, 0.18), transparent 54%);
  background-size: 125% 125%, 120% 120%, 130% 130%, 122% 122%;
  animation: app-bg-blobs-orbit 24s ease-in-out infinite !important;
}

[data-testid="stApp"]::after {
  content: "" !important;
  position: fixed !important;
  left: 50% !important;
  top: 50% !important;
  width: 220vmax !important;
  height: 220vmax !important;
  margin-left: -110vmax !important;
  margin-top: -110vmax !important;
  z-index: 0 !important;
  pointer-events: none !important;
  opacity: 0.1 !important;
  mix-blend-mode: screen !important;
  background: conic-gradient(
    from 210deg at 50% 50%,
    rgba(35, 110, 155, 0.22),
    rgba(70, 65, 125, 0.16),
    rgba(115, 45, 85, 0.18),
    rgba(25, 95, 115, 0.17),
    rgba(55, 85, 145, 0.15),
    rgba(35, 110, 155, 0.22)
  );
  animation: app-bg-conic-drift 40s linear infinite !important;
}

[data-testid="stAppViewContainer"],
[data-testid="stSidebar"],
[data-testid="stHeader"],
[data-testid="stDecoration"],
[data-testid="stToolbar"],
[data-testid="stMain"],
section[data-testid="stSidebar"],
section[data-testid="stMain"],
[data-testid="stBottom"] {
  position: relative !important;
  z-index: 1 !important;
}

@keyframes app-bg-base-shift {
  0%, 100% {
    background-position: 10% 8%, 90% 12%, 8% 45%, center;
  }
  25% {
    background-position: 85% 20%, 15% 30%, 92% 55%, center;
  }
  50% {
    background-position: 40% 85%, 75% 8%, 45% 12%, center;
  }
  75% {
    background-position: 12% 55%, 92% 78%, 70% 88%, center;
  }
}

@keyframes app-bg-blobs-orbit {
  0%, 100% {
    transform: translate(0, 0) rotate(0deg) scale(1);
    background-position: 22% 28%, 85% 22%, 72% 90%, 8% 82%;
  }
  25% {
    transform: translate(5vw, -4vh) rotate(5deg) scale(1.06);
    background-position: 78% 18%, 12% 58%, 88% 42%, 52% 22%;
  }
  50% {
    transform: translate(-4vw, 6vh) rotate(-4deg) scale(1.03);
    background-position: 38% 78%, 88% 12%, 28% 88%, 86% 68%;
  }
  75% {
    transform: translate(-6vw, -3vh) rotate(6deg) scale(1.07);
    background-position: 8% 48%, 52% 82%, 68% 18%, 22% 78%;
  }
}

@keyframes app-bg-conic-drift {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  [data-testid="stApp"],
  html,
  body {
    animation: none !important;
    background-position: 10% 8%, 90% 12%, 40% 50%, center !important;
  }
  [data-testid="stApp"]::before {
    animation: none !important;
    transform: none !important;
    opacity: 0.26 !important;
    background-position: 50% 50%, 50% 50%, 50% 50%, 50% 50% !important;
  }
  [data-testid="stApp"]::after {
    animation: none !important;
    opacity: 0.06 !important;
  }
}

[data-testid="stApp"] .stMainBlockContainer.main {
  padding-top: 0.85rem !important;
}

[data-testid="stApp"] .block-container {
  padding: 2rem clamp(1rem, 3vw, 2.75rem) 3rem !important;
  max-width: 1480px !important;
}

[data-testid="stApp"] header,
[data-testid="stHeader"] {
  background: rgba(4, 6, 12, 0.62) !important;
  backdrop-filter: blur(18px) saturate(1.2);
  border-bottom: 1px solid rgba(148,163,184,0.14) !important;
}

[data-testid="stSidebar"],
section[data-testid="stSidebar"] {
  background: linear-gradient(185deg, rgba(4, 6, 12, 0.72) 0%, rgba(7, 11, 22, 0.82) 100%) !important;
  backdrop-filter: blur(22px) saturate(1.25);
  border-right: 1px solid rgba(148,163,184,0.15) !important;
  box-shadow: 4px 0 36px rgba(0,0,0,0.35);
}

[data-testid="stSidebar"] *,
[data-testid="stSidebar"] label {
  color: #cbd5e1 !important;
}

.hero-wrap {
  margin-bottom: 0.5rem !important;
  padding-bottom: 0 !important;
}

p.hero-title {
  font-family: ui-sans-serif, system-ui, sans-serif !important;
  font-weight: 680 !important;
  letter-spacing: -0.03em !important;
  font-size: clamp(1.65rem, 2.4vw, 2.1rem) !important;
  line-height: 1.2 !important;
  margin: 0 0 0.35rem 0 !important;
  color: #f8fafc !important;
}

.hero-title .accent {
  display: inline-block;
  background-image: linear-gradient(
    100deg,
    #38bdf8 0%,
    #818cf8 22%,
    #e879f9 44%,
    #22d3ee 66%,
    #a78bfa 82%,
    #38bdf8 100%
  );
  background-size: 260% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: hero-accent-flow 7s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .hero-title .accent {
    animation: none !important;
    background-position: 0 50% !important;
  }
}

@keyframes hero-accent-flow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 100% 50%;
  }
}

p.hero-sub {
  color: #94a3b8 !important;
  font-size: 0.95rem !important;
  margin: 0 !important;
  letter-spacing: 0.01em;
}

[data-testid="stVerticalBlockBorderWrapper"] {
  background:
    linear-gradient(165deg, rgba(30, 41, 59, 0.55) 0%, rgba(15, 23, 42, 0.72) 45%, rgba(8, 12, 22, 0.85) 100%) !important;
  border: 1px solid rgba(56, 189, 248, 0.14) !important;
  border-radius: 20px !important;
  padding: 1.35rem 1.35rem 1.45rem !important;
  backdrop-filter: blur(14px) saturate(1.35);
  box-shadow:
    inset 0 1px 0 rgba(255,255,255,0.07),
    0 10px 40px rgba(0, 0, 0, 0.45),
    0 0 0 1px rgba(15, 23, 42, 0.6);
}

.section-head {
  font-size: 0.72rem !important;
  font-weight: 650 !important;
  letter-spacing: 0.22em !important;
  text-transform: uppercase !important;
  color: #7dd3fc !important;
  margin: 0 0 1.25rem 0 !important;
  padding-bottom: 0.55rem !important;
  border-bottom: none !important;
  background: linear-gradient(90deg, rgba(56,189,248,0.15), transparent 65%);
  padding: 0.35rem 0.65rem !important;
  border-radius: 8px !important;
  border-left: 3px solid rgba(56, 189, 248, 0.85) !important;
}

[data-testid="column"] [data-testid="stMetricContainer"] {
  min-width: min(100%, 10.5rem) !important;
}

[data-testid="stHorizontalBlock"] [data-testid="stMetricContainer"] {
  min-width: min(100%, 11rem) !important;
}

/* Snapshot KPI rows: equal columns when row holds metrics (:has avoids touching chart/tool layouts). */
[data-testid="stHorizontalBlock"]:has([data-testid="stMetricContainer"]) {
  gap: 0.75rem !important;
  align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetricContainer"]) > [data-testid="column"] {
  flex: 1 1 0% !important;
  min-width: 0 !important;
}
[data-testid="stHorizontalBlock"]:has([data-testid="stMetricContainer"]) [data-testid="stMetricContainer"] {
  width: 100% !important;
  min-width: 0 !important;
  max-width: none !important;
  box-sizing: border-box !important;
}

[data-testid="column"] {
  overflow: visible !important;
}

[data-testid="stHorizontalBlock"] {
  overflow: visible !important;
  gap: 0.65rem !important;
}

[data-testid="stMetricContainer"],
[data-testid="stMetric"] {
  position: relative !important;
  isolation: isolate !important;
  background:
    linear-gradient(155deg, rgba(51, 65, 85, 0.38) 0%, rgba(23, 33, 54, 0.82) 42%, rgba(15, 23, 42, 0.96) 100%) !important;
  border: 1px solid rgba(148, 163, 184, 0.16) !important;
  border-radius: 18px !important;
  padding: 1rem 1.25rem 1.15rem 1.15rem !important;
  overflow: visible !important;
  min-height: 6.9rem !important;
  box-shadow:
    inset 4px 0 0 0 rgba(56, 189, 248, 0.85),
    inset 0 1px 0 rgba(255, 255, 255, 0.06),
    0 10px 28px -6px rgba(0, 0, 0, 0.55),
    0 0 24px -8px rgba(56, 189, 248, 0.12);
  transition: transform 0.22s ease, box-shadow 0.22s ease;
}

[data-testid="stMetricContainer"]:hover {
  transform: translateY(-3px);
  box-shadow:
    inset 4px 0 0 0 rgba(129, 140, 248, 0.95),
    inset 0 1px 0 rgba(255, 255, 255, 0.08),
    0 16px 36px -8px rgba(0, 0, 0, 0.55),
    0 0 36px -6px rgba(129, 140, 248, 0.18);
}

[data-testid="stMetricContainer"] button {
  opacity: 0.38 !important;
  transition: opacity 0.18s ease !important;
}

[data-testid="stMetricContainer"]:hover button {
  opacity: 0.72 !important;
}

[data-testid="stMetricLabel"] *,
[data-testid="stMetricLabel"] label,
[data-testid="stMetricLabel"] div,
[data-testid="stMetricLabel"] p {
  color: #a5b4c9 !important;
  font-size: 0.76rem !important;
  font-weight: 520 !important;
  text-transform: none !important;
  letter-spacing: 0.015em !important;
  line-height: 1.42 !important;
  white-space: normal !important;
  overflow: visible !important;
  text-overflow: unset !important;
  word-wrap: break-word !important;
  overflow-wrap: anywhere !important;
  hyphens: manual !important;
}

[data-testid="stMetricLabel"] {
  display: block !important;
  min-height: 2.55rem !important;
}

[data-testid="stMetricValue"],
[data-testid="stMetricValue"] *,
[data-testid="stMetricValue"] div {
  margin-top: 0.15rem !important;
  color: #f8fafc !important;
  -webkit-text-fill-color: #f8fafc !important;
  background: none !important;
  font-weight: 740 !important;
  font-size: 1.82rem !important;
  letter-spacing: -0.025em !important;
  font-variant-numeric: tabular-nums;
  overflow: visible !important;
  text-overflow: unset !important;
  white-space: nowrap !important;
  text-shadow: 0 2px 22px rgba(56, 189, 248, 0.22);
}

[data-testid="stMetricContainer"] [data-testid="stMarkdownContainer"] {
  overflow: visible !important;
}

.stApp hr,
div[data-testid="stVerticalBorder"] hr {
  border: none !important;
  border-top: 1px solid rgba(148,163,184,0.16) !important;
  margin: 1.25rem 0 !important;
}

.js-plotly-plot .plotly .modebar {
  border-radius: 8px !important;
  background: rgba(15,23,42,0.65) !important;
}

/* Metric explorer tabs — dark bar, cyan active label + underline */
[data-testid="stTabs"] {
  margin-top: 0.25rem !important;
}
[data-testid="stTabs"] [role="tablist"] {
  background: transparent !important;
  border-bottom: 1px solid rgba(148, 163, 184, 0.22) !important;
  gap: 0.15rem !important;
  padding: 0 !important;
}
[data-testid="stTabs"] [role="tab"] {
  color: #e2e8f0 !important;
  font-weight: 600 !important;
  letter-spacing: 0.02em !important;
  border: none !important;
  border-radius: 0 !important;
  padding: 0.65rem 1.15rem 0.55rem 1.15rem !important;
  margin: 0 !important;
  background: transparent !important;
  cursor: pointer !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  color: #22d3ee !important;
  border-bottom: 2px solid #22d3ee !important;
}
[data-testid="stTabs"] [role="tab"]:focus-visible {
  box-shadow: none !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
  color: #f1f5f9 !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"]:hover {
  color: #22d3ee !important;
}

/* Inner labels sometimes keep cursor:help when ``title`` is set — force arrow pointer */
[data-testid="stTabs"] [role="tab"] *,
[data-testid="stTabs"] [role="tablist"] * {
  cursor: pointer !important;
}

/* Fallback — Base Web tabs (some Streamlit builds) */
.stTabs [data-baseweb="tab-list"] {
  border-bottom: 1px solid rgba(148, 163, 184, 0.22) !important;
  gap: 0.15rem !important;
  background: transparent !important;
}
.stTabs [data-baseweb="tab"] {
  color: #e2e8f0 !important;
  font-weight: 600 !important;
  border-radius: 0 !important;
  border-bottom: 2px solid transparent !important;
  padding: 0.65rem 1.15rem 0.55rem 1.15rem !important;
  cursor: pointer !important;
}
.stTabs [data-baseweb="tab"][aria-selected="true"] {
  color: #22d3ee !important;
  border-bottom-color: #22d3ee !important;
}
.stTabs [data-baseweb="tab"] * {
  cursor: pointer !important;
}

/* Snapshot KPI cards — playful hover stories (custom HTML, replaces st.metric in Snapshot) */
[data-testid="stHorizontalBlock"]:has(.snap-kpi-wrap) {
  gap: 0.75rem !important;
  align-items: stretch !important;
}
[data-testid="stHorizontalBlock"]:has(.snap-kpi-wrap) > [data-testid="column"] {
  flex: 1 1 0% !important;
  min-width: 0 !important;
}

.snap-kpi-wrap {
  position: relative;
  width: 100%;
  min-height: 7.35rem;
  margin-bottom: 0.1rem;
  border-radius: 20px;
  outline: none !important;
}

.snap-kpi-face {
  position: relative;
  z-index: 1;
  min-height: 7.35rem;
  padding: 0.95rem 1.05rem 1rem 1rem;
  border-radius: 20px;
  box-sizing: border-box;
  background:
    linear-gradient(142deg, rgba(72, 85, 120, 0.42) 0%, rgba(30, 41, 72, 0.82) 48%, rgba(15, 23, 42, 0.98) 100%);
  border: 1px solid rgba(148, 163, 184, 0.22);
  box-shadow:
    inset 5px 0 0 0 rgba(56, 189, 248, 0.92),
    inset 0 1px 0 rgba(255, 255, 255, 0.07),
    0 10px 30px rgba(0, 0, 0, 0.5),
    0 0 28px rgba(56, 189, 248, 0.11);
  transition:
    transform 0.28s cubic-bezier(0.34, 1.56, 0.64, 1),
    box-shadow 0.28s ease,
    border-color 0.28s ease;
}

.snap-kpi-wrap:hover .snap-kpi-face,
.snap-kpi-wrap:focus-within .snap-kpi-face {
  transform: translateY(-5px) scale(1.03);
  border-color: rgba(125, 211, 252, 0.58);
  box-shadow:
    inset 5px 0 0 0 rgba(244, 114, 182, 0.92),
    0 0 0 1px rgba(56, 189, 248, 0.46),
    0 18px 46px rgba(56, 189, 248, 0.24),
    0 14px 40px rgba(0, 0, 0, 0.55);
}

.snap-kpi-label {
  margin: 0 0 0.5rem 0;
  min-height: 2.85rem;
}

.snap-kpi-label-text {
  display: inline-block;
  width: 100%;
  font-size: clamp(1.08rem, 2.15vw, 1.48rem);
  font-weight: 700;
  letter-spacing: -0.022em;
  line-height: 1.28;
  background-image: linear-gradient(
    100deg,
    #38bdf8 0%,
    #818cf8 18%,
    #e879f9 38%,
    #22d3ee 58%,
    #f472b6 78%,
    #a78bfa 92%,
    #38bdf8 100%
  );
  background-size: 300% 100%;
  background-clip: text;
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  animation: snap-kpi-title-flow 6.5s linear infinite;
}

@media (prefers-reduced-motion: reduce) {
  .snap-kpi-label-text {
    animation: none !important;
    background-position: 0% 50% !important;
  }
}

@keyframes snap-kpi-title-flow {
  0% {
    background-position: 0% 50%;
  }
  100% {
    background-position: 100% 50%;
  }
}

.snap-kpi-value {
  font-size: 1.88rem !important;
  font-weight: 760 !important;
  letter-spacing: -0.03em !important;
  color: #f8fafc !important;
  text-shadow: 0 2px 26px rgba(56, 189, 248, 0.28);
  font-variant-numeric: tabular-nums;
}

.snap-kpi-blurb {
  position: absolute;
  inset: 0;
  z-index: 4;
  border-radius: 20px;
  padding: 0.85rem 0.75rem;
  box-sizing: border-box;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  font-size: 0.78rem !important;
  line-height: 1.48 !important;
  font-weight: 480 !important;
  color: #dbeafe !important;
  background: rgba(6, 10, 18, 0.94);
  border: 1px solid rgba(56, 189, 248, 0.52);
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.26s ease, visibility 0.26s ease;
}

.snap-kpi-wrap:hover .snap-kpi-blurb,
.snap-kpi-wrap:focus-within .snap-kpi-blurb {
  opacity: 1;
  visibility: visible;
}

@media (prefers-reduced-motion: reduce) {
  .snap-kpi-face {
    transition: none !important;
  }
  .snap-kpi-wrap:hover .snap-kpi-face,
  .snap-kpi-wrap:focus-within .snap-kpi-face {
    transform: none !important;
  }
}

.bw-grid-heading {
  font-size: 0.88rem !important;
  font-weight: 650 !important;
  letter-spacing: 0.05em !important;
  color: #cbd5e1 !important;
  margin: 0.85rem 0 0.5rem 0 !important;
}

.bw-grid-heading:first-child {
  margin-top: 0 !important;
}
[data-testid="stPlotlyChart"] .js-plotly-plot svg text {
  stroke: none !important;
  stroke-width: 0 !important;
  paint-order: fill stroke !important;
}

/* Avoid OS “high contrast” / forced-colors overriding Plotly SVG fills */
[data-testid="stPlotlyChart"],
[data-testid="stPlotlyChart"] .js-plotly-plot {
  forced-color-adjust: none !important;
  color-scheme: dark !important;
}

/* Glide Data Grid headers ignore pandas thead CSS — they use theme-driven CSS variables */
[data-testid="stDataFrame"] {
  --gdg-bg-header: #000000 !important;
  --gdg-bg-header-has-focus: #000000 !important;
  --gdg-text-group-header: #D1D5DB !important;
}

/* Wider modal for BW snapshot dialog — fits more month columns for screenshots */
[data-testid="stDialogContent"] {
  max-width: min(96vw, 2200px) !important;
  width: min(96vw, 2200px) !important;
}
</style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(show_spinner=True)
def cached_employees(path: str) -> pd.DataFrame:
    return analytics.load_employees(path)


def _load_raw_employees() -> tuple[pd.DataFrame, str]:
    """Return roster dataframe and a short label for the hero line (uploaded CSV or Excel path)."""
    uploaded = st.session_state.get(analytics.STREAMLIT_UPLOADED_DF_KEY)
    if uploaded is not None:
        name = st.session_state.get(analytics.STREAMLIT_UPLOADED_NAME_KEY) or "Uploaded CSV"
        return uploaded, str(name)
    path = analytics.resolve_data_path()
    if not path.exists():
        st.error(
            f"No dataset available. Use **Upload CSV dataset** in the sidebar to load a file, "
            f"or place the workbook at `{path}` (or set `BEVERAGE_FACTORY_XLSX`)."
        )
        st.stop()
    try:
        return cached_employees(str(path)), path.name
    except FileNotFoundError:
        st.error(f"Excel file not found: `{path}`.")
        st.stop()
    except Exception as e:
        st.error(f"Could not read Excel `{path}`: {e}")
        st.stop()


def render_csv_upload_body(*, key_prefix: str) -> None:
    """Pick CSV → validate → store in session (used from sidebar expander or Upload page)."""
    with st.expander("Required column headers", expanded=False):
        st.code(
            ", ".join(analytics.EMPLOYEE_REQUIRED_COLUMNS) + ", Quick Quits (optional)",
            language=None,
        )

    uploaded = st.file_uploader(
        "CSV file",
        type=["csv"],
        key=f"{key_prefix}_csv_file",
        help="Same columns as the Employees sheet export.",
    )

    if uploaded is None:
        return

    raw_bytes = uploaded.getvalue()
    try:
        preview = pd.read_csv(io.BytesIO(raw_bytes), nrows=12)
        st.dataframe(preview, width="stretch", hide_index=True)
    except Exception as e:
        st.warning(f"Could not preview CSV: {e}")

    ac1, ac2 = st.columns(2)
    with ac1:
        if st.button("Apply — use everywhere", type="primary", key=f"{key_prefix}_apply"):
            try:
                df = analytics.load_employees_csv(io.BytesIO(raw_bytes))
                st.session_state[analytics.STREAMLIT_UPLOADED_DF_KEY] = df
                st.session_state[analytics.STREAMLIT_UPLOADED_NAME_KEY] = uploaded.name
                st.success(f"Loaded **{len(df):,}** rows from `{uploaded.name}`.")
                st.rerun()
            except ValueError as e:
                st.error(str(e))
            except Exception as e:
                st.error(f"Could not load CSV: {e}")
    with ac2:
        if st.button("Clear upload", key=f"{key_prefix}_clear_upload"):
            st.session_state.pop(analytics.STREAMLIT_UPLOADED_DF_KEY, None)
            st.session_state.pop(analytics.STREAMLIT_UPLOADED_NAME_KEY, None)
            st.rerun()


_EXPLORE_METRIC_KEYS: tuple[tuple[str, str], ...] = (
    ("New hires", "hires"),
    ("Departures", "departures"),
    ("Quick quits", "quick_quits"),
    ("Headcount", "headcount"),
    ("Involuntary vs voluntary", "inv_vol"),
    ("Terminated reason", "terminated_reason"),
)


def _inject_explore_tab_hover_tooltips(tab_title_by_label: dict[str, str]) -> None:
    """Attach native ``title`` tooltips to Explore tabs.

    Uses ``st.html`` with ``unsafe_allow_javascript=True`` so the script runs in the **main**
    document. ``components.v1.html`` runs inside a sandboxed iframe, which often blocks
    ``window.parent.document``, so tab titles never applied there.
    """
    order_json = json.dumps([lbl for lbl, _ in _EXPLORE_METRIC_KEYS])
    tips_json = json.dumps(tab_title_by_label)
    st.html(
        f"""<div aria-hidden="true" style="display:none;height:0;width:0;overflow:hidden"></div>
<script>
(function () {{
  const ORDER = {order_json};
  const TIPS = {tips_json};
  function tabLabel(el) {{
    return (el && (el.innerText || el.textContent || "")).replace(/\\s+/g, " ").trim();
  }}
  function pickTabs(doc) {{
    const wanted = ORDER;
    const lists = doc.querySelectorAll('[role="tablist"]');
    for (const list of lists) {{
      const tabs = Array.from(list.querySelectorAll('[role="tab"]'));
      if (tabs.length !== wanted.length) continue;
      const labels = tabs.map(tabLabel);
      let ok = true;
      for (let i = 0; i < wanted.length; i++) {{
        if (labels[i] !== wanted[i]) {{ ok = false; break; }}
      }}
      if (ok) return tabs;
    }}
    const byLabel = new Map();
    for (const el of doc.querySelectorAll('[role="tab"]')) {{
      const txt = tabLabel(el);
      if (wanted.includes(txt) && !byLabel.has(txt)) byLabel.set(txt, el);
    }}
    if (wanted.every((l) => byLabel.has(l))) return wanted.map((l) => byLabel.get(l));
    return [];
  }}
  function apply() {{
    try {{
      const tabs = pickTabs(document);
      for (const btn of tabs) {{
        const txt = tabLabel(btn);
        if (Object.prototype.hasOwnProperty.call(TIPS, txt)) {{
          btn.setAttribute("title", TIPS[txt]);
        }}
      }}
    }} catch (e) {{}}
  }}
  let scheduled = null;
  function queue() {{
    if (scheduled) return;
    scheduled = requestAnimationFrame(function () {{
      scheduled = null;
      apply();
    }});
  }}
  if (window.__bfExploreTabTipObs) {{
    try {{ window.__bfExploreTabTipObs.disconnect(); }} catch (e) {{}}
  }}
  window.__bfExploreTabTipObs = new MutationObserver(queue);
  window.__bfExploreTabTipObs.observe(document.body, {{ childList: true, subtree: true }});
  queue();
  setTimeout(queue, 50);
  setTimeout(queue, 400);
  setTimeout(queue, 1200);
}})();
</script>""",
        unsafe_allow_javascript=True,
    )


def _explore_period_from_state(
    tab_key: str, reference: pd.Timestamp, raw: pd.DataFrame
) -> pd.Period | None:
    """Rolling vs single month for metrics whose picker is not shown this run (uses widget session keys)."""
    mode = st.session_state.get(f"explore_{tab_key}_mode")
    if mode is None or (isinstance(mode, str) and mode.startswith("Rolling")):
        return None
    y = st.session_state.get(f"explore_{tab_key}_y")
    m = st.session_state.get(f"explore_{tab_key}_m")
    if y is None or m is None:
        return pd.Period(f"{reference.year}-{reference.month:02d}", freq="M")
    try:
        return pd.Period(f"{int(y)}-{int(m):02d}", freq="M")
    except (TypeError, ValueError):
        return pd.Period(f"{reference.year}-{reference.month:02d}", freq="M")


def _bw_title_suffix(period_opt: pd.Period | None, reference: pd.Timestamp) -> str:
    """Matches analytics BW titles: rolling vs ``May '24`` style label."""
    if period_opt is None:
        return "rolling last 12 months"
    hp = pd.Period(period_opt, freq="M")
    return analytics.period_column_labels(pd.PeriodIndex([hp], freq="M"))[0]


def _explore_period_picker(
    tab_key: str,
    reference: pd.Timestamp,
    raw: pd.DataFrame,
    *,
    radio_label: str = "Charts in this tab use",
) -> pd.Period | None:
    """Rolling L12M through reference month, or one calendar month — independent per metric."""
    mode = st.radio(
        radio_label,
        ["Rolling last 12 months", "Single calendar month"],
        horizontal=True,
        key=f"explore_{tab_key}_mode",
        help=(
            "Rolling window ends on the sidebar reference month. Single month shows one column "
            "(all departments / reasons)."
        ),
    )
    if mode.startswith("Rolling"):
        return None
    dmin = raw["Start Date"].min()
    dmx = pd.concat([raw["Start Date"], raw["Departure Date"]], ignore_index=True).max()
    min_y = int(dmin.year) if pd.notna(dmin) else reference.year - 3
    max_y = int(max(reference.year, pd.Timestamp(dmx).year)) if pd.notna(dmx) else reference.year
    years = list(range(min_y, max_y + 1)) or [reference.year]
    iy = years.index(reference.year) if reference.year in years else len(years) - 1
    c1, c2 = st.columns(2)
    with c1:
        y = st.selectbox(
            "Year",
            years,
            index=iy,
            key=f"explore_{tab_key}_y",
        )
    with c2:
        m = st.selectbox(
            "Month",
            list(range(1, 13)),
            index=int(reference.month) - 1,
            format_func=lambda mo: analytics.MONTH_LABELS[mo - 1],
            key=f"explore_{tab_key}_m",
        )
    return pd.Period(f"{y}-{m:02d}", freq="M")


def _section_heading(text: str) -> None:
    st.markdown(f'<p class="section-head">{html.escape(text)}</p>', unsafe_allow_html=True)


def _snapshot_kpi_card(label: str, value: str, *, story: str) -> None:
    """Glass KPI tile: large animated-gradient title + hover/focus story overlay."""
    safe_label = html.escape(label, quote=True)
    st.markdown(
        f'<div class="snap-kpi-wrap" tabindex="0" role="group" aria-label="{safe_label}">'
        f'<div class="snap-kpi-face">'
        f'<div class="snap-kpi-label"><span class="snap-kpi-label-text">{html.escape(label)}</span></div>'
        f'<div class="snap-kpi-value">{html.escape(value)}</div></div>'
        f'<div class="snap-kpi-blurb">{html.escape(story)}</div></div>',
        unsafe_allow_html=True,
    )


def _bw_column_config(df: pd.DataFrame) -> dict[str, object]:
    """Streamlit Arrow tables default numeric columns to right alignment; label column left."""
    cfg: dict[str, object] = {}
    cols = list(df.columns)
    for i, col in enumerate(cols):
        if pd.api.types.is_numeric_dtype(df[col]):
            cfg[col] = NumberColumn(alignment="center")
        else:
            cfg[col] = TextColumn(alignment="left" if i == 0 else "center")
    return cfg


@st.dialog("Department × month — full table", width="large")
def _bw_fullscreen_snapshot_dialog(heading: str, disp: pd.DataFrame) -> None:
    """Scaled HTML table — fits entire grid in view without inner scrollbars (slides screenshots)."""
    st.markdown(f"### {heading}")
    st.caption(
        "Table scales to fit this window — **no scrolling** inside the preview. "
        "Capture with your screenshot tool, then close."
    )
    styled = analytics.style_bw_dataframe(disp)
    table_html = styled.to_html(notebook=False, index=False)

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<style>
  html, body {{
    margin: 0;
    padding: 0;
    background: #0B0E14;
    overflow: hidden;
    height: 100%;
    width: 100%;
    color: #D1D5DB;
  }}
  #root {{
    box-sizing: border-box;
    padding: 12px 12px 16px 12px;
    width: 100%;
    min-height: calc(100vh - 28px);
    height: calc(100vh - 28px);
    display: flex;
    align-items: flex-start;
    justify-content: center;
    overflow: hidden;
  }}
  #fit {{
    transform-origin: top center;
    display: inline-block;
    line-height: 1.25;
    max-width: 100%;
  }}
  table.dataframe {{
    border-collapse: collapse !important;
    border-spacing: 0 !important;
  }}
  table.dataframe th,
  table.dataframe td {{
    box-sizing: border-box !important;
  }}
</style>
</head>
<body>
<div id="root"><div id="fit">{table_html}</div></div>
<script>
(function () {{
  function fit() {{
    var root = document.getElementById("root");
    var fit = document.getElementById("fit");
    if (!root || !fit) return;
    fit.style.transform = "none";
    fit.style.margin = "0 auto";
    var bw = fit.scrollWidth;
    var bh = fit.scrollHeight;
    if (!bw || !bh) return;
    var pad = 16;
    var rw = root.clientWidth - pad;
    var rh = root.clientHeight - pad;
    if (rw <= 0 || rh <= 0) return;
    var s = Math.min(rw / bw, rh / bh, 1) * 0.985;
    fit.style.transform = "scale(" + s + ")";
    var sw = Math.ceil(bw * s);
    var sh = Math.ceil(bh * s);
    root.style.minHeight = (sh + pad) + "px";
    root.style.height = (sh + pad) + "px";
  }}
  function runFit() {{
    fit();
    requestAnimationFrame(fit);
    setTimeout(fit, 50);
    setTimeout(fit, 200);
  }}
  window.addEventListener("load", runFit);
  window.addEventListener("resize", fit);
  if (document.fonts && document.fonts.ready) {{
    document.fonts.ready.then(runFit);
  }}
  runFit();
}})();
</script>
</body>
</html>"""

    components.html(html, height=960, scrolling=False)


def _streamlit_bw_grid(
    matrix: pd.DataFrame | None,
    *,
    title: str | None = None,
    height: int = 680,
    snapshot_key: str | None = None,
) -> None:
    """Department × month grid via HTML/CSS (Total row white-on-black is reliable vs Plotly SVG quirks)."""
    disp = analytics.bw_matrix_with_total(matrix)
    if disp is None or disp.empty:
        if title:
            st.markdown(
                f'<p class="bw-grid-heading">{title}</p>',
                unsafe_allow_html=True,
            )
        st.caption("No data in this window.")
        return

    sk = snapshot_key or (
        "bw_" + hashlib.sha256((title or "grid").encode("utf-8")).hexdigest()[:14]
    )

    if title:
        st.markdown(
            f'<p class="bw-grid-heading">{title}</p>',
            unsafe_allow_html=True,
        )
    open_full = st.button(
        "Full table — screenshot view",
        key=f"{sk}_fullscreen_snap",
        help="Opens a wide full-height view of this grid so you can screenshot it for slides.",
        type="secondary",
    )
    styled_matrix = analytics.style_bw_dataframe(disp)
    bw_cfg = _bw_column_config(styled_matrix.data)
    # Ensure the implicit RangeIndex column is not shown beside Department/months.
    bw_cfg["_index"] = None
    st.dataframe(
        styled_matrix,
        width="stretch",
        height=min(height, 52 + 28 * len(styled_matrix.data)),
        column_config=bw_cfg,
        hide_index=True,
        key=f"{sk}_bw_df",
    )
    if open_full:
        _bw_fullscreen_snapshot_dialog(title or "Department × month", disp)


def _streamlit_yoy_outlook(fig: object | None, *, key: str) -> None:
    """Renders the dashed YoY outlook chart below the department × month grid (rolling tabs only)."""
    if fig is None:
        return
    st.markdown(
        '<p class="bw-grid-heading">Trend outlook (illustrative)</p>',
        unsafe_allow_html=True,
    )
    st.caption(
        "Projection blends current-year trend with the **prior YoY year’s** calendar-month pattern "
        "(anchored at your latest actual), plus a conservative floor — illustrative only."
    )
    st.plotly_chart(fig, width="stretch", config=_PLOT_CFG, theme=None, key=key)


def main() -> None:
    st.set_page_config(
        page_title="HR Ops / HRBPs Dashboard",
        page_icon="◆",
        layout="wide",
    )
    _inject_style()

    try:
        st.sidebar.page_link(
            "pages/1_Upload_data.py",
            label="Upload page (full screen)",
            icon="⬆",
        )
    except Exception:
        st.sidebar.caption(
            "Tip: upload also lives in **⬆ Upload CSV (replace dataset)** below (sidebar link needs a recent Streamlit)."
        )

    raw, data_source_label = _load_raw_employees()

    if st.session_state.get(analytics.STREAMLIT_UPLOADED_DF_KEY) is not None:
        st.sidebar.caption(f"Dataset: **{data_source_label}** ({len(raw):,} rows)")
        if st.sidebar.button("Clear uploaded CSV", key="clear_uploaded_csv_btn"):
            st.session_state.pop(analytics.STREAMLIT_UPLOADED_DF_KEY, None)
            st.session_state.pop(analytics.STREAMLIT_UPLOADED_NAME_KEY, None)
            st.rerun()
    else:
        _p = analytics.resolve_data_path()
        st.sidebar.caption(f"Dataset: Excel `{_p.name}`")

    with st.sidebar.expander("⬆ Upload CSV (replace dataset)", expanded=False):
        st.caption("Replaces Excel for **Snapshot** + **Explore** until cleared.")
        render_csv_upload_body(key_prefix="sidebar")

    default_ref = pd.Timestamp.today().normalize()
    st.sidebar.markdown(
        "**Reference date:** Explore charts default to rolling windows through this month when you choose "
        "**Rolling last 12 months**."
    )

    reference = pd.Timestamp(st.sidebar.date_input("Reference date", value=default_ref.date()))

    # Range for historic picks — widgets stay mounted every rerun (avoids Streamlit duplicate-ID issues).
    dmin = raw["Start Date"].min()
    dmx = pd.concat([raw["Start Date"], raw["Departure Date"]], ignore_index=True).max()
    min_y = int(dmin.year) if pd.notna(dmin) else reference.year - 3
    max_y = int(max(reference.year, pd.Timestamp(dmx).year)) if pd.notna(dmx) else reference.year
    years = list(range(min_y, max_y + 1)) or [reference.year]
    iy = years.index(reference.year) if reference.year in years else len(years) - 1

    historic_kpis = st.sidebar.checkbox(
        "Historic KPI snapshot",
        value=False,
        key="historic_kpi_checkbox",
        help=(
            "Use hire and departure dates to compute KPIs **as of the last day** of a chosen month/year. "
            "Rolling hires / departures / quick quits use the 12 calendar months ending then. "
            "When unchecked, Snapshot KPIs match your Excel **User Status** counts at any reference date "
            "(same as before)."
        ),
    )
    st.sidebar.caption("Historic month (used only when Historic KPI snapshot is on)")
    hy = st.sidebar.selectbox(
        "Year",
        years,
        index=iy,
        key="historic_kpi_year",
    )
    hm = st.sidebar.selectbox(
        "Month",
        list(range(1, 13)),
        index=int(reference.month) - 1,
        format_func=lambda mo: analytics.MONTH_LABELS[mo - 1],
        key="historic_kpi_month",
    )

    kpi_ref_label = ""
    if historic_kpis:
        kpi_ref = analytics.month_end_timestamp(int(hy), int(hm))
        kpis = analytics.snapshot_metrics_as_of(raw, kpi_ref)
        kpi_ref_label = f"{analytics.MONTH_LABELS[int(hm) - 1]} {int(hy)}"
    else:
        kpis = analytics.snapshot_metrics(raw, reference)

    with st.container(border=True):
        st.markdown(
            '<p class="hero-title"><span class="accent">HR Ops / HRBPs Dashboard</span></p>',
            unsafe_allow_html=True,
        )
        st.markdown(
            (
                f'<p class="hero-sub">{html.escape(data_source_label)} &nbsp;•&nbsp; KPI snapshot '
                f"<strong>as of end of {html.escape(kpi_ref_label)}</strong> "
                f"(historic) &nbsp;•&nbsp; <strong>{len(raw):,}</strong> people in dataset</p>"
                if historic_kpis
                else f'<p class="hero-sub">{html.escape(data_source_label)} &nbsp;•&nbsp; reference '
                f"<strong>{reference.date()}</strong> "
                f"&nbsp;•&nbsp; <strong>{len(raw):,}</strong> people in dataset</p>"
            ),
            unsafe_allow_html=True,
        )
        st.caption(
            "Replace the roster from a CSV: open **⬆ Upload CSV (replace dataset)** in the left sidebar "
            "(below the dataset line)."
        )

        st.markdown("---")
        _section_heading("Snapshot")
        st.caption(
            "Hover a card (or Tab to focus it) for a plain-language read on what moves each number. "
            "Titles use a moving gradient."
        )
        if historic_kpis:
            st.caption(
                f"Roster row (**active / inactive / total**) is reconstructed from **Start Date** and "
                f"**Departure Date** through **{kpi_ref_label}**. Rolling metrics use the **12 months ending** "
                "that month."
            )
        r1a, r1b, r1c, r1d = st.columns(4)
        rm = kpi_ref_label
        if historic_kpis:
            story_tenure = (
                f"This is the average tenure of everyone who was still employed on the last day of {rm}. "
                "For each person we measure hire date through that month-end in days, divide by 365.25, then "
                "average. Heavy hiring pulls this down (lots of short tenures); strong retention and slower hiring "
                "usually lift it."
            )
            story_active = (
                f"People hired on or before the end of {rm} who had not yet departed on or before that day — "
                "rebuilt from Start Date and Departure Date, not from the Excel User Status column."
            )
            story_inactive = (
                f"People who had started on or before the end of {rm} and whose departure happened on or before "
                "that same month-end. It grows when exits concentrate in recent months."
            )
            story_total = (
                f"Everyone with a hire date on or before the end of {rm} (whether still active or already exited "
                "by then). This is the historic cohort size driving the rows above."
            )
            story_hires = (
                f"Counts hire rows whose hire-month falls in the twelve calendar months ending {rm}. "
                "Spikes when recruiting fills many roles in that window; quiet hiring shows up as a softer total."
            )
            story_dep = (
                f"Counts inactive exits whose departure-month falls in the twelve months ending {rm}. "
                "Rises with reorganizations, seasonality, or turnover bursts; falls when fewer dated departures land "
                "in that window."
            )
            story_qq = (
                f"Quick-quit exits (Quick Quits = Yes) with departure-month in the twelve months ending {rm}. "
                "This is a subset of departures — useful for early attrition hot spots."
            )
            story_net = (
                f"Hires minus departures over the twelve months ending {rm}, using the same hire/exit rules as "
                "the cards beside this one. Positive means more people joined than left in that stretch; negative "
                "means net shrink."
            )
        else:
            story_tenure = (
                "Average tenure for rows marked Active on this extract: days from hire through your sidebar "
                "reference date, divided by 365.25, averaged. Shifts when new hires or exits change the active mix."
            )
            story_active = (
                "Straight count of employees with User Status Active on this dataset — reflects how HR labeled "
                "the roster when the file was pulled."
            )
            story_inactive = (
                "Employees marked Inactive on the extract. Useful as a counterpart to Active; big moves usually "
                "track bulk exits or data cleanup."
            )
            story_total = (
                "Every row in the file (all statuses). It's simply the roster size represented in this workbook "
                "upload."
            )
            story_hires = (
                "Hires whose hire-month sits in the rolling last twelve calendar months ending on your sidebar "
                "reference month — recruitment velocity for that window."
            )
            story_dep = (
                "Inactive employees with a departure date in that same rolling twelve-month window — how many "
                "dated exits landed recently."
            )
            story_qq = (
                'Departures flagged Quick Quits = Yes inside that window — early churn layered on top of overall exits.'
            )
            story_net = (
                "Hires minus departures in that rolling window. Think of it as net workforce motion from starts vs "
                "stops — positive signals expansion, negative signals contraction."
            )

        with r1a:
            _snapshot_kpi_card(
                "Avg tenure — active (years)",
                analytics.format_tenure_years_display(float(kpis["tenure_years"])),
                story=story_tenure,
            )
        with r1b:
            _snapshot_kpi_card(
                "Active employees",
                analytics.format_count_display(kpis["active_count"]),
                story=story_active,
            )
        with r1c:
            _snapshot_kpi_card(
                "Inactive employees",
                analytics.format_count_display(kpis["inactive_count"]),
                story=story_inactive,
            )
        with r1d:
            _snapshot_kpi_card(
                "Total on roster",
                analytics.format_count_display(kpis["total_count"]),
                story=story_total,
            )
        r2a, r2b, r2c, r2d = st.columns(4)
        with r2a:
            _snapshot_kpi_card(
                "Hires (L12M)",
                analytics.format_count_display(kpis["hires_last_12"]),
                story=story_hires,
            )
        with r2b:
            _snapshot_kpi_card(
                "Departures (L12M)",
                analytics.format_count_display(kpis["departures_last_12"]),
                story=story_dep,
            )
        with r2c:
            _snapshot_kpi_card(
                "Quick quits (L12M)",
                analytics.format_count_display(kpis["quick_quits_last_12"]),
                story=story_qq,
            )
        with r2d:
            _snapshot_kpi_card(
                "Net hires − exits (L12M)",
                analytics.format_count_display(kpis["net_change_last_12"]),
                story=story_net,
            )

    with st.container(border=True):
        _section_heading("Explore metrics")
        st.caption(
            "**Trend outlook:** On **Rolling last 12 months**, the dashed outlook appears **below** the "
            "department × month grid (not on the YoY chart above). It blends the comparison-year trend with "
            "**prior-year** same-calendar-month deltas anchored at your latest actual. It applies when the "
            "sidebar reference month is **before December**. **Single calendar month** uses YoY bars only — "
            "no outlook."
        )
        st.caption(
            (
                "Each tab uses the **sidebar reference date** for rolling windows. Snapshot KPIs above follow "
                f"**historic month {kpi_ref_label}** when enabled."
                if historic_kpis
                else (
                    "Each tab uses the **sidebar reference date** for rolling windows. Snapshot KPIs match "
                    "that reference (or enable **Historic KPI snapshot** in the sidebar)."
                )
            )
        )
        explore_hover_parts = analytics.explore_metric_tab_hover_parts(raw, reference)
        explore_tab_hover_native = {
            lab: f"{blurb}\n\n{metric}"
            for lab, (blurb, metric) in explore_hover_parts.items()
        }
        periods: dict[str, pd.Period | None] = {}
        tab_h, tab_d, tab_q, tab_hc, tab_x, tab_term = st.tabs(
            [
                "New hires",
                "Departures",
                "Quick quits",
                "Headcount",
                "Involuntary vs voluntary",
                "Terminated reason",
            ],
            key="explore_metric_tabs",
        )
        _inject_explore_tab_hover_tooltips(explore_tab_hover_native)

        with tab_h:
            with st.container(key="explore_picker_hires"):
                periods["hires"] = _explore_period_picker("hires", reference, raw)
        with tab_d:
            with st.container(key="explore_picker_departures"):
                periods["departures"] = _explore_period_picker("departures", reference, raw)
        with tab_q:
            with st.container(key="explore_picker_quick_quits"):
                periods["quick_quits"] = _explore_period_picker("quick_quits", reference, raw)
        with tab_hc:
            with st.container(key="explore_picker_headcount"):
                periods["headcount"] = _explore_period_picker("headcount", reference, raw)
        with tab_x:
            with st.container(key="explore_picker_inv_vol"):
                periods["inv_vol"] = _explore_period_picker("inv_vol", reference, raw)
        with tab_term:
            with st.container(key="explore_picker_term_reason"):
                periods["terminated_reason"] = _explore_period_picker(
                    "terminated_reason", reference, raw
                )

        kpi_as_of_ts = None
        if historic_kpis:
            kpi_as_of_ts = analytics.month_end_timestamp(int(hy), int(hm))

        _, figs, bw_mats, outlook_figs = analytics.build_dashboard_figures(
            raw, reference, periods=periods, kpis_as_of=kpi_as_of_ts
        )
        (
            f_hi_out,
            f_dep_out,
            f_qq_out,
            f_hc_out,
        ) = outlook_figs
        (
            f_hi_y,
            f_dep_y,
            f_qq_y,
            f_hc_yoy,
            f_exit_iv,
            f_term,
            *_plotly_bw_tables,
        ) = figs
        (
            hire_mat,
            dep_mat,
            qq_mat,
            hc_mat,
            exit_mat,
            inv_dept_mat,
            vol_dept_mat,
            term_reason_mat,
        ) = bw_mats

        tw_h = _bw_title_suffix(periods["hires"], reference)
        tw_d = _bw_title_suffix(periods["departures"], reference)
        tw_q = _bw_title_suffix(periods["quick_quits"], reference)
        tw_hc = _bw_title_suffix(periods["headcount"], reference)
        tw_iv = _bw_title_suffix(periods["inv_vol"], reference)
        tw_tr = _bw_title_suffix(periods["terminated_reason"], reference)

        with tab_h:
            with st.container(key="explore_body_hires"):
                st.caption(
                    f"Snapshot KPI hires L12M: **{analytics.format_count_display(kpis['hires_last_12'])}** · "
                    f"reference **{reference.date()}**. YoY chart window: **{tw_h}**."
                )
                st.plotly_chart(
                    f_hi_y,
                    width="stretch",
                    config=_PLOT_CFG,
                    theme=None,
                    key="explore_chart_hires",
                )
                _streamlit_bw_grid(
                    hire_mat,
                    title=f"New hires — department × month ({tw_h})",
                    snapshot_key="expl_bw_hires",
                )
                with st.container(border=True):
                    st.markdown(
                        analytics.explore_new_hires_narrative_markdown(
                            raw,
                            reference,
                            periods["hires"],
                            hire_matrix=hire_mat,
                        )
                    )
                    st.caption(
                        "**Actual** uses this tab’s calendar scope: **Single calendar month** counts hires in that "
                        "picked month; **Rolling last 12 months** uses the sidebar **reference month**."
                    )
                _streamlit_yoy_outlook(f_hi_out, key="explore_outlook_hires")

        with tab_d:
            with st.container(key="explore_body_departures"):
                st.caption(
                    f"Snapshot KPI departures L12M: **{analytics.format_count_display(kpis['departures_last_12'])}**. "
                    f"YoY chart window: **{tw_d}**."
                )
                st.plotly_chart(
                    f_dep_y,
                    width="stretch",
                    config=_PLOT_CFG,
                    theme=None,
                    key="explore_chart_departures",
                )
                _streamlit_bw_grid(
                    dep_mat,
                    title=f"Departures — department × month ({tw_d})",
                    snapshot_key="expl_bw_dep",
                )
                with st.container(border=True):
                    st.markdown(
                        analytics.explore_departures_narrative_markdown(
                            raw,
                            reference,
                            periods["departures"],
                            departure_matrix=dep_mat,
                        )
                    )
                    st.caption(
                        "**Actual** uses this tab’s calendar scope: **Single calendar month** counts departures "
                        "in that picked month; **Rolling last 12 months** uses the sidebar **reference month**."
                    )
                _streamlit_yoy_outlook(f_dep_out, key="explore_outlook_dep")

        with tab_q:
            with st.container(key="explore_body_quick_quits"):
                st.caption(
                    f"Snapshot KPI quick-quits L12M: **{analytics.format_count_display(kpis['quick_quits_last_12'])}**. "
                    f"YoY chart window: **{tw_q}**."
                )
                st.plotly_chart(
                    f_qq_y,
                    width="stretch",
                    config=_PLOT_CFG,
                    theme=None,
                    key="explore_chart_quick_quits",
                )
                _streamlit_bw_grid(
                    qq_mat,
                    title=f"Quick quits — department × month ({tw_q})",
                    snapshot_key="expl_bw_qq",
                )
                with st.container(border=True):
                    st.markdown(
                        analytics.explore_quick_quits_narrative_markdown(
                            raw,
                            reference,
                            periods["quick_quits"],
                        )
                    )
                    st.caption(
                        "**Target** is fixed at **0** (goal: no quick-quit exits). **Actual** uses this tab’s "
                        "calendar scope: **Single calendar month** counts quick quits in that picked month; "
                        "**Rolling last 12 months** uses the sidebar **reference month**. Voluntary vs involuntary "
                        "comes from termination-reason bucketing (same as elsewhere in this app)."
                    )
                _streamlit_yoy_outlook(f_qq_out, key="explore_outlook_qq")

        with tab_hc:
            with st.container(key="explore_body_headcount"):
                st.caption(
                    f"Active roster **{analytics.format_count_display(kpis['active_count'])}** at reference. "
                    f"Grid window: **{tw_hc}**. "
                    "YoY chart: **total month-end headcount** (same as the table Total row) by calendar month."
                )
                st.plotly_chart(
                    f_hc_yoy,
                    width="stretch",
                    config=_PLOT_CFG,
                    theme=None,
                    key="explore_chart_headcount_yoy_totals",
                )
                _streamlit_bw_grid(
                    hc_mat,
                    title=f"Headcount (active, month-end) — department × month ({tw_hc})",
                    snapshot_key="expl_bw_hc",
                )
                with st.container(border=True):
                    st.markdown(
                        analytics.explore_headcount_narrative_markdown(
                            raw,
                            reference,
                            periods["headcount"],
                        )
                    )
                    st.caption(
                        "Based on **active roster at month-end** (same logic as the grid). Compares this month to "
                        "the **prior calendar month**. Recruiting-spend line uses **`BEVERAGE_RECRUITING_SPEND_PCT`** "
                        "(default **1.5**) as an illustrative ratio—not computed from this roster file."
                    )
                _streamlit_yoy_outlook(f_hc_out, key="explore_outlook_hc")

        with tab_x:
            with st.container(key="explore_body_inv_vol"):
                st.caption(
                    f"Exit-class grids (`analytics.classify_exit_type`). This tab window: **{tw_iv}**."
                )
                st.plotly_chart(
                    f_exit_iv,
                    width="stretch",
                    config=_PLOT_CFG,
                    theme=None,
                    key="explore_chart_inv_vol",
                )
                _streamlit_bw_grid(
                    inv_dept_mat,
                    title=f"Involuntary exits — department × month ({tw_iv})",
                    snapshot_key="expl_bw_inv_dept",
                )
                _streamlit_bw_grid(
                    vol_dept_mat,
                    title=f"Voluntary exits — department × month ({tw_iv})",
                    snapshot_key="expl_bw_vol_dept",
                )
                _streamlit_bw_grid(
                    exit_mat,
                    title=f"Exit type × month ({tw_iv})",
                    snapshot_key="expl_bw_exit_type",
                )

        with tab_term:
            with st.container(key="explore_body_term_reason"):
                st.caption(
                    f"Termination reason totals (**bar chart**) and Reason × month grid for **{tw_tr}**."
                )
                st.plotly_chart(
                    f_term,
                    width="stretch",
                    config=_PLOT_CFG,
                    theme=None,
                    key="explore_chart_term_reason",
                )
                _streamlit_bw_grid(
                    term_reason_mat,
                    title=f"Terminated Reason × month — inactive exits ({tw_tr})",
                    height=920,
                    snapshot_key="expl_bw_term_reason",
                )


if __name__ == "__main__":
    main()
