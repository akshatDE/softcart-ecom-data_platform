"""Tab 3 — Sales channel and promotion analytics charts.

Answers: which products sell best on which channel, and whether promotions
drive volume or mainly erode revenue through discounts.
"""

from __future__ import annotations

from typing import Callable

import pandas as pd
import plotly.express as px
import streamlit as st

Fetcher = Callable[..., pd.DataFrame]


def render(fetch: Fetcher) -> None:
    """Render the channel & promotion tab."""
    channels = fetch("channel-performance")
    if channels.empty:
        st.info("No channel data available yet.")
        return

    left, right = st.columns(2)
    with left:
        st.plotly_chart(
            px.bar(channels, x="channel_name", y="net_revenue",
                   color="channel_type", title="Net revenue by sales channel"),
            use_container_width=True,
        )
    with right:
        st.plotly_chart(
            px.bar(channels, x="channel_name", y="quantity_sold",
                   color="channel_type", title="Quantity sold by sales channel"),
            use_container_width=True,
        )

    matrix = fetch("channel-product-matrix", limit=5)
    if not matrix.empty:
        st.subheader("Best-selling products per channel")
        st.plotly_chart(
            px.bar(matrix, x="net_revenue", y="channel_name", color="product_name",
                   orientation="h", title="Top 5 products by channel (net revenue)"),
            use_container_width=True,
        )
        st.dataframe(matrix, use_container_width=True, hide_index=True)

    promos = fetch("promotion-performance")
    if promos.empty:
        return
    st.subheader("Promotion effectiveness")
    baseline = promos[promos["promotion_code"] == "NONE"]
    promoted = promos[promos["promotion_code"] != "NONE"]

    if not baseline.empty and not promoted.empty:
        cols = st.columns(3)
        cols[0].metric("Promo orders", f"{int(promoted['orders'].sum()):,}")
        cols[1].metric("Promo discount cost", f"${promoted['discounts'].sum():,.0f}")
        avg_promo = promoted["avg_items_per_line"].mean()
        avg_base = baseline["avg_items_per_line"].mean()
        cols[2].metric(
            "Avg items/line (promo vs none)",
            f"{avg_promo:.2f} vs {avg_base:.2f}",
            delta=f"{avg_promo - avg_base:+.2f}",
        )

    st.plotly_chart(
        px.scatter(
            promoted, x="discounts", y="quantity_sold",
            size="gross_revenue", color="discount_type",
            hover_name="promotion_code",
            title="Discount spend vs volume per promotion "
                  "(up-left = efficient, down-right = margin-eroding)",
        ),
        use_container_width=True,
    )
    st.plotly_chart(
        px.bar(
            promoted.sort_values("net_revenue", ascending=False),
            x="promotion_code", y=["gross_revenue", "discounts", "net_revenue"],
            barmode="group", title="Gross revenue, discounts and net revenue by promotion",
        ),
        use_container_width=True,
    )
