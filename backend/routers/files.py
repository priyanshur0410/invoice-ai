"""
Files Router
GET  /api/files/              - List all uploaded files with status
GET  /api/files/{file_id}     - Get file metadata + processing status
DELETE /api/files/{file_id}   - Delete file and associated invoice data
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.database import get_db, InvoiceFile, Invoice, InvoiceLineItem
import uuid

router = APIRouter()


@router.get("/")
async def list_files(
    skip: int = 0,
    limit: int = 50,
    status: str = None,
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(InvoiceFile)
        .order_by(desc(InvoiceFile.created_at))
        .offset(skip)
        .limit(limit)
    )
    if status:
        query = query.where(InvoiceFile.status == status)

    result = await db.execute(query)
    files = result.scalars().all()
    return [_file_to_dict(f) for f in files]


@router.get("/{file_id}")
async def get_file(file_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InvoiceFile).where(InvoiceFile.id == file_id)
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(404, "File not found")

    # Also fetch associated invoice if done
    inv_result = await db.execute(
        select(Invoice).where(Invoice.file_id == file_id)
    )
    invoice = inv_result.scalar_one_or_none()

    data = _file_to_dict(f)
    if invoice:
        data["invoice"] = {
            "id": str(invoice.id),
            "invoice_number": invoice.invoice_number,
            "vendor_name": invoice.vendor_normalized or invoice.vendor_name,
            "total": invoice.total,
            "currency": invoice.currency,
            "confidence_score": invoice.confidence_score,
            "is_duplicate": invoice.is_duplicate,
        }
    return data


@router.delete("/{file_id}")
async def delete_file(file_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(InvoiceFile).where(InvoiceFile.id == file_id)
    )
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(404, "File not found")

    # Cascade delete invoice + line items
    inv_result = await db.execute(
        select(Invoice).where(Invoice.file_id == file_id)
    )
    invoice = inv_result.scalar_one_or_none()
    if invoice:
        li_result = await db.execute(
            select(InvoiceLineItem).where(InvoiceLineItem.invoice_id == invoice.id)
        )
        for li in li_result.scalars().all():
            await db.delete(li)
        await db.delete(invoice)

    await db.delete(f)
    await db.commit()

    return {"message": "File and associated data deleted", "file_id": file_id}


@router.get("/stats/overview")
async def file_stats(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import func
    result = await db.execute(
        select(
            InvoiceFile.status,
            func.count(InvoiceFile.id).label("count"),
        ).group_by(InvoiceFile.status)
    )
    rows = result.all()
    return {row.status: row.count for row in rows}


def _file_to_dict(f: InvoiceFile) -> dict:
    return {
        "id": str(f.id),
        "filename": f.original_filename,
        "file_url": f.file_url,
        "file_type": f.file_type,
        "file_size": f.file_size,
        "status": f.status,
        "created_at": f.created_at.isoformat() if f.created_at else None,
        "processed_at": f.processed_at.isoformat() if f.processed_at else None,
    }
