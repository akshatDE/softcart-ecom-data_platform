"""SoftCart executive analytics dashboard (Streamlit).

Fetches everything through the FastAPI layer — the dashboard never touches
DuckDB directly, mirroring a production separation between the serving API
and the presentation layer.

Global sidebar filters (date range, category, channel) are merged into every
API call, so the KPI header and all tabs re-slice together.

Run locally with::

    streamlit run src/main/dashboard/streamlit_app.py
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

import pandas as pd
import requests
import streamlit as st

from src.main.dashboard.components import channel_charts, customer_charts, product_charts
from src.main.utility.config_loader import get_config
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

API_BASE_URL = get_config().get("dashboard", "api_base_url")


@st.cache_data(ttl=300, show_spinner=False)
def fetch(endpoint: str, **params: Any) -> pd.DataFrame:
    """GET one analytics endpoint and return its data as a DataFrame."""
    url = f"{API_BASE_URL}/analytics/{endpoint}"
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return pd.DataFrame(response.json()["data"])


@st.cache_data(ttl=300, show_spinner=False)
def fetch_filter_options() -> dict[str, Any]:
    """GET the available filter values for the sidebar."""
    response = requests.get(f"{API_BASE_URL}/analytics/filter-options", timeout=30)
    response.raise_for_status()
    return response.json()["data"]


def ask_nlp(question: str) -> dict[str, Any]:
    """POST a natural-language question to the NLP-to-SQL endpoint."""
    response = requests.post(
        f"{API_BASE_URL}/nlp/query", json={"question": question}, timeout=180
    )
    if response.status_code != 200:
        detail = response.json().get("detail", response.text)
        raise RuntimeError(detail)
    return response.json()


def render_sidebar() -> dict[str, Any]:
    """Sidebar filter controls; returns query params for the API."""
    options = fetch_filter_options()
    min_date = date.fromisoformat(options["min_date"])
    max_date = date.fromisoformat(options["max_date"])

    st.sidebar.header("🔍 Filters")
    date_range = st.sidebar.date_input(
        "Order date range",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        help="Bounds every KPI and chart on the page.",
    )
    categories = st.sidebar.multiselect(
        "Categories", options["categories"],
        placeholder="All categories",
    )
    channels = st.sidebar.multiselect(
        "Sales channels", options["channels"],
        placeholder="All channels",
    )
    if st.sidebar.button("Reset filters", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    params: dict[str, Any] = {}
    # date_input returns a 1-tuple while the user is mid-selection.
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start, end = date_range
        if start != min_date:
            params["start_date"] = start.isoformat()
        if end != max_date:
            params["end_date"] = end.isoformat()
    if categories:
        params["category"] = categories
    if channels:
        params["channel"] = channels

    if params:
        active = []
        if "start_date" in params or "end_date" in params:
            active.append(
                f"{params.get('start_date', min_date)} → {params.get('end_date', max_date)}"
            )
        if categories:
            active.append(", ".join(categories))
        if channels:
            active.append(", ".join(channels))
        st.sidebar.success("Active: " + " · ".join(active))
    else:
        st.sidebar.caption("Showing all data.")
    return params


def make_filtered_fetch(filter_params: dict[str, Any]) -> Callable[..., pd.DataFrame]:
    """Wrap ``fetch`` so every call inherits the sidebar filters."""

    def filtered(endpoint: str, **params: Any) -> pd.DataFrame:
        return fetch(endpoint, **{**filter_params, **params})

    return filtered


def render_header(fetch_data: Callable[..., pd.DataFrame], filtered: bool) -> None:
    """Headline KPI strip (respects active filters)."""
    kpis = fetch_data("kpi-summary")
    if kpis.empty or pd.isna(kpis.iloc[0]["net_revenue"]):
        st.warning(
            "No data for the current filter selection — widen the filters, "
            "or run the pipeline if the warehouse is empty."
        )
        st.stop()
    row = kpis.iloc[0]
    cols = st.columns(6)
    cols[0].metric("Net revenue", f"${row['net_revenue']:,.0f}")
    cols[1].metric("Gross revenue", f"${row['gross_revenue']:,.0f}")
    cols[2].metric("Discounts", f"${row['total_discounts']:,.0f}")
    cols[3].metric("Refunds", f"${row['refunds']:,.0f}")
    cols[4].metric("Orders", f"{int(row['orders']):,}")
    cols[5].metric("Customers", f"{int(row['customers']):,}")
    if filtered:
        st.caption("KPIs reflect the active sidebar filters.")


def render_nlp_tab() -> None:
    """AI-assisted ad-hoc querying tab (not affected by sidebar filters)."""
    st.subheader("Ask the warehouse (AI)")
    st.caption(
        "Questions are translated to a single read-only SELECT over the star "
        "schema by a local Ollama model, validated, and executed with a row "
        "limit and timeout. The generated SQL is always shown. Sidebar "
        "filters do not apply here — put constraints in your question."
    )
    examples = [
        "What were the top 10 products by revenue last month?",
        "Which categories had declining sales over time?",
        "Show repeat customer revenue by month.",
        "Which promotions increased quantity sold but reduced net revenue?",
    ]
    question = st.text_input("Your question", placeholder=examples[0])
    st.caption("Examples: " + " · ".join(examples))
    if st.button("Ask", type="primary") and question:
        with st.spinner("Generating and validating SQL..."):
            try:
                result = ask_nlp(question)
            except (requests.RequestException, RuntimeError) as exc:
                st.error(f"Could not answer: {exc}")
                return
        st.code(result["sql"], language="sql")
        frame = pd.DataFrame(result["rows"])
        st.dataframe(frame, use_container_width=True)
        st.caption(f"{result['row_count']} rows returned")


def main() -> None:
    """Compose the dashboard."""
    st.set_page_config(page_title="SoftCart Analytics", page_icon="🛒", layout="wide")
    st.title("🛒 SoftCart Analytics")

    try:
        filter_params = render_sidebar()
    except requests.RequestException as exc:
        st.error(f"Analytics API is not reachable at {API_BASE_URL}: {exc}")
        st.stop()

    fetch_data = make_filtered_fetch(filter_params)
    render_header(fetch_data, filtered=bool(filter_params))

    tab_products, tab_customers, tab_channels, tab_ai = st.tabs(
        ["📦 Products & Categories", "👥 Customers & Concentration",
         "📣 Channels & Promotions", "🤖 Ask AI"]
    )
    with tab_products:
        product_charts.render(fetch_data)
    with tab_customers:
        customer_charts.render(fetch_data)
    with tab_channels:
        channel_charts.render(fetch_data)
    with tab_ai:
        render_nlp_tab()

    refresh = fetch("last-refresh")
    if not refresh.empty:
        st.caption(f"Analytics last rebuilt: {refresh.iloc[0]['completed_at']}")


if __name__ == "__main__":
    main()
