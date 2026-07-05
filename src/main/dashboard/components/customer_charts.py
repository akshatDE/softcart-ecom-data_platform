"""Tab 2 — Customer behaviour and revenue concentration charts.

Answers: repeat vs one-time buyers, spending tiers, top customers, CLV
distribution, and Pareto-style revenue concentration.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import plotly.express as px
import streamlit as st

Fetcher = Callable[..., pd.DataFrame]


def render(fetch: Fetcher) -> None:
    """Render the customer & concentration tab."""
    left, right = st.columns(2)

    repeat = fetch("repeat-vs-one-time")
    with left:
        if not repeat.empty:
            st.plotly_chart(
                px.pie(repeat, names="buyer_type", values="customers",
                       title="Repeat vs one-time buyers (customer count)"),
                use_container_width=True,
            )
            st.dataframe(repeat, use_container_width=True, hide_index=True)

    segments = fetch("customer-segments")
    with right:
        if not segments.empty:
            st.plotly_chart(
                px.bar(segments, x="spending_tier", y="net_revenue",
                       color="spending_tier",
                       title="Net revenue by customer spending tier"),
                use_container_width=True,
            )

    clv = fetch("clv-distribution")
    if not clv.empty:
        st.plotly_chart(
            px.histogram(clv, x="lifetime_value", nbins=50,
                         title="Customer lifetime value distribution"),
            use_container_width=True,
        )

    left, right = st.columns(2)
    with left:
        product_curve = fetch("revenue-concentration", entity="product")
        if not product_curve.empty:
            st.plotly_chart(
                _pareto_figure(product_curve, "Product revenue concentration (Pareto)"),
                use_container_width=True,
            )
    with right:
        customer_curve = fetch("revenue-concentration", entity="customer")
        if not customer_curve.empty:
            st.plotly_chart(
                _pareto_figure(customer_curve, "Customer revenue concentration (Pareto)"),
                use_container_width=True,
            )

    top = fetch("top-customers", limit=15)
    if not top.empty:
        st.subheader("Top customers by lifetime value")
        st.dataframe(top, use_container_width=True, hide_index=True)


def _pareto_figure(curve: pd.DataFrame, title: str):
    """Cumulative revenue share vs entity share, with an 80% guide line."""
    figure = px.line(
        curve, x="entity_pct", y="cumulative_revenue_pct", title=title,
        labels={"entity_pct": "% of entities (ranked by revenue)",
                "cumulative_revenue_pct": "% of cumulative revenue"},
    )
    figure.add_hline(y=80, line_dash="dash", annotation_text="80% of revenue")
    return figure
