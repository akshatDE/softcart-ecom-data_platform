"""REST endpoints for pre-built analytics queries.

Every endpoint accepts optional global filters so the dashboard can slice
the whole page consistently:

* ``start_date`` / ``end_date`` — ISO dates bounding the order date;
* ``category`` — repeatable, filters on parent category;
* ``channel`` — repeatable, filters on sales channel name.
"""

from __future__ import annotations

from datetime import date
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException, Query

from src.main.services.analytics_service import AnalyticsService, QueryFilters
from src.main.utility.exceptions import SoftCartError
from src.main.utility.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])


def query_filters(
    start_date: date | None = Query(None, description="Orders on/after this date"),
    end_date: date | None = Query(None, description="Orders on/before this date"),
    category: list[str] | None = Query(None, description="Parent categories to include"),
    channel: list[str] | None = Query(None, description="Sales channels to include"),
) -> QueryFilters:
    """Assemble the shared filter set from query parameters."""
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must be <= end_date")
    return QueryFilters(
        start_date=start_date,
        end_date=end_date,
        categories=tuple(category or ()),
        channels=tuple(channel or ()),
    )


def _serve(query_name: str, fetch: Callable[[AnalyticsService], Any]) -> dict[str, Any]:
    """Run one analytics query with uniform error handling."""
    service = AnalyticsService()
    try:
        data = fetch(service)
        return {"query": query_name, "row_count": len(data), "data": data}
    except SoftCartError as exc:
        logger.error("Analytics endpoint {} failed: {}", query_name, exc)
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        service.close()


@router.get("/filter-options")
def filter_options() -> dict[str, Any]:
    """Available filter values (date bounds, categories, channels)."""
    service = AnalyticsService()
    try:
        return {"query": "filter_options", "data": service.filter_options()}
    except SoftCartError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        service.close()


@router.get("/kpi-summary")
def kpi_summary(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Headline KPIs (orders, revenue, discounts, refunds)."""
    return _serve("kpi_summary", lambda s: s.kpi_summary(filters))


@router.get("/revenue-by-category")
def revenue_by_category(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Revenue and quantity by category."""
    return _serve("revenue_by_category", lambda s: s.revenue_by_category(filters))


@router.get("/revenue-by-product")
def revenue_by_product(
    limit: int = Query(20, ge=1, le=200),
    filters: QueryFilters = Depends(query_filters),
) -> dict[str, Any]:
    """Top products by net revenue."""
    return _serve("revenue_by_product", lambda s: s.revenue_by_product(limit, filters))


@router.get("/sales-trend")
def sales_trend(
    granularity: str = Query("month", pattern="^(month|day)$"),
    filters: QueryFilters = Depends(query_filters),
) -> dict[str, Any]:
    """Sales trend over time (monthly or daily)."""
    return _serve("sales_trend", lambda s: s.sales_trend(granularity, filters))


@router.get("/category-trend")
def category_trend(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Monthly revenue per parent category."""
    return _serve("category_trend", lambda s: s.category_trend(filters))


@router.get("/customer-segments")
def customer_segments(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Customer spending tiers."""
    return _serve("customer_segments", lambda s: s.customer_segments(filters))


@router.get("/repeat-vs-one-time")
def repeat_vs_one_time(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Repeat versus one-time buyer split."""
    return _serve("repeat_vs_one_time", lambda s: s.repeat_vs_one_time(filters))


@router.get("/top-customers")
def top_customers(
    limit: int = Query(20, ge=1, le=200),
    filters: QueryFilters = Depends(query_filters),
) -> dict[str, Any]:
    """Highest lifetime-value customers."""
    return _serve("top_customers", lambda s: s.top_customers(limit, filters))


@router.get("/revenue-concentration")
def revenue_concentration(
    entity: str = Query("product", pattern="^(product|customer)$"),
    filters: QueryFilters = Depends(query_filters),
) -> dict[str, Any]:
    """Pareto-style cumulative revenue concentration."""
    return _serve("revenue_concentration", lambda s: s.revenue_concentration(entity, filters))


@router.get("/clv-distribution")
def clv_distribution(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Customer lifetime value per customer."""
    return _serve("clv_distribution", lambda s: s.clv_distribution(filters))


@router.get("/channel-performance")
def channel_performance(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Revenue and volume per sales channel."""
    return _serve("channel_performance", lambda s: s.channel_performance(filters))


@router.get("/channel-product-matrix")
def channel_product_matrix(
    limit: int = Query(5, ge=1, le=20),
    filters: QueryFilters = Depends(query_filters),
) -> dict[str, Any]:
    """Best-selling products per channel."""
    return _serve("channel_product_matrix", lambda s: s.channel_product_matrix(limit, filters))


@router.get("/promotion-performance")
def promotion_performance(filters: QueryFilters = Depends(query_filters)) -> dict[str, Any]:
    """Volume versus discount cost per promotion."""
    return _serve("promotion_performance", lambda s: s.promotion_performance(filters))


@router.get("/last-refresh")
def last_refresh() -> dict[str, Any]:
    """Timestamp of the most recent analytics build."""
    return _serve("last_refresh", lambda s: s.last_refresh())
