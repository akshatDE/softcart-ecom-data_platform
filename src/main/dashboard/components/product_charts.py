"""Tab 1 — Product and category performance charts.

Answers: which categories/products drive revenue vs quantity, how sales
trend over time, and gross vs net revenue by category.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import plotly.express as px
import streamlit as st

Fetcher = Callable[..., pd.DataFrame]


def render(fetch: Fetcher) -> None:
    """Render the product & category performance tab."""
    categories = fetch("revenue-by-category")
    if categories.empty:
        st.info("No category data available yet.")
        return

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(categories, x="category_name", y="net_revenue",
                   color="parent_category", title="Net revenue by category"),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            px.bar(categories, x="category_name", y="quantity_sold",
                   color="parent_category", title="Quantity sold by category"),
            use_container_width=True,
        )

    st.plotly_chart(
        px.bar(
            categories.melt(
                id_vars="category_name",
                value_vars=["gross_revenue", "net_revenue"],
                var_name="measure", value_name="revenue",
            ),
            x="category_name", y="revenue", color="measure", barmode="group",
            title="Gross vs net revenue by category (gap = discounts)",
        ),
        use_container_width=True,
    )

    top_products = fetch("revenue-by-product", limit=15)
    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(top_products, x="net_revenue", y="product_name",
                   orientation="h", title="Top products by net revenue"),
            use_container_width=True,
        )
    with right:
        by_quantity = top_products.sort_values("quantity_sold", ascending=False)
        st.plotly_chart(
            px.bar(by_quantity, x="quantity_sold", y="product_name",
                   orientation="h", title="Top products by quantity sold"),
            use_container_width=True,
        )

    trend = fetch("category-trend")
    if not trend.empty:
        st.plotly_chart(
            px.line(trend, x="period", y="net_revenue", color="parent_category",
                    title="Category revenue trend (monthly)"),
            use_container_width=True,
        )

    overall = fetch("sales-trend", granularity="month")
    if not overall.empty:
        st.plotly_chart(
            px.area(overall, x="period", y="net_revenue",
                    title="Overall net revenue trend (monthly)"),
            use_container_width=True,
        )
