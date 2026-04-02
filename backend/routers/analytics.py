"""
Analytics Router
GET /api/analytics/summary          - Overall stats
GET /api/analytics/vendor-spend     - Total spend per vendor
GET /api/analytics/monthly-trend    - Month-wise spend
GET /api/analytics/currency-totals  - Per-currency breakdown
GET /api/analytics/top-vendors      - Top N vendors by spend
"""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract
from models.database import get_db, Invoice
import datetime

router = APIRouter()


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)):
    total_result = await db.execute(
        select(
            func.count(Invoice.id).label("total_invoices"),
            func.sum(Invoice.total).label("total_spend"),
            func.avg(Invoice.confidence_score).label("avg_confidence"),
            func.count(func.distinct(Invoice.vendor_normalized)).label("unique_vendors"),
        )
    )
    row = total_result.one()

    dup_result = await db.execute(
        select(func.count(Invoice.id)).where(Invoice.is_duplicate == True)
    )
    duplicates = dup_result.scalar() or 0

    return {
        "total_invoices": row.total_invoices or 0,
        "total_spend": round(float(row.total_spend or 0), 2),
        "avg_confidence": round(float(row.avg_confidence or 0), 3),
        "unique_vendors": row.unique_vendors or 0,
        "duplicate_count": duplicates,
    }


@router.get("/vendor-spend")
async def vendor_spend(limit: int = 20, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Invoice.vendor_normalized,
            func.count(Invoice.id).label("invoice_count"),
            func.sum(Invoice.total).label("total_spend"),
            Invoice.currency,
        )
        .group_by(Invoice.vendor_normalized, Invoice.currency)
        .order_by(func.sum(Invoice.total).desc())
        .limit(limit)
    )
    rows = result.all()
    return [
        {
            "vendor": row.vendor_normalized or "Unknown",
            "invoice_count": row.invoice_count,
            "total_spend": round(float(row.total_spend or 0), 2),
            "currency": row.currency,
        }
        for row in rows
    ]


@router.get("/monthly-trend")
async def monthly_trend(
    months: int = 12,
    db: AsyncSession = Depends(get_db),
):
    since = datetime.datetime.utcnow() - datetime.timedelta(days=months * 31)
    result = await db.execute(
        select(
            extract("year", Invoice.invoice_date).label("year"),
            extract("month", Invoice.invoice_date).label("month"),
            func.sum(Invoice.total).label("total_spend"),
            func.count(Invoice.id).label("invoice_count"),
        )
        .where(Invoice.invoice_date >= since)
        .group_by("year", "month")
        .order_by("year", "month")
    )
    rows = result.all()
    return [
        {
            "year": int(row.year),
            "month": int(row.month),
            "month_label": datetime.date(int(row.year), int(row.month), 1).strftime("%b %Y"),
            "total_spend": round(float(row.total_spend or 0), 2),
            "invoice_count": row.invoice_count,
        }
        for row in rows
    ]


@router.get("/currency-totals")
async def currency_totals(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Invoice.currency,
            func.sum(Invoice.total).label("total"),
            func.count(Invoice.id).label("count"),
        )
        .group_by(Invoice.currency)
        .order_by(func.sum(Invoice.total).desc())
    )
    rows = result.all()
    return [
        {
            "currency": row.currency,
            "total": round(float(row.total or 0), 2),
            "count": row.count,
        }
        for row in rows
    ]


@router.get("/top-vendors")
async def top_vendors(n: int = 5, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(
            Invoice.vendor_normalized,
            func.sum(Invoice.total).label("spend"),
        )
        .group_by(Invoice.vendor_normalized)
        .order_by(func.sum(Invoice.total).desc())
        .limit(n)
    )
    rows = result.all()
    return [
        {"vendor": row.vendor_normalized or "Unknown", "spend": round(float(row.spend or 0), 2)}
        for row in rows
    ]
