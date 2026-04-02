"""
Invoice Router
POST /api/invoices/upload       - Upload & process invoice(s)
GET  /api/invoices/             - List all invoices
GET  /api/invoices/{id}         - Get single invoice
POST /api/invoices/batch        - Batch upload
GET  /api/invoices/{id}/retry   - Retry failed extraction
"""
import uuid
import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from models.database import get_db, InvoiceFile, Invoice, InvoiceLineItem
from services.ocr_service import ocr_service
from services.llm_service import llm_service
from services.template_service import template_service
from services.storage_service import storage_service

router = APIRouter()

MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
ALLOWED_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/jpg"}


async def process_invoice_file(file_id: str, db: AsyncSession):
    """Background task: OCR → template detect → LLM parse → save."""
    result = await db.execute(select(InvoiceFile).where(InvoiceFile.id == file_id))
    invoice_file = result.scalar_one_or_none()
    if not invoice_file:
        return

    try:
        # Update status
        invoice_file.status = "processing"
        await db.commit()

        # Download file bytes (from Supabase URL in real app; mocked here)
        # In production: fetch from invoice_file.file_url
        # For demo: file_bytes stored temporarily; here we re-read from a temp cache
        import aiofiles, os
        temp_path = f"/tmp/{file_id}"
        async with aiofiles.open(temp_path, "rb") as f:
            file_bytes = await f.read()
        os.remove(temp_path)

        # OCR
        ocr_result = await ocr_service.extract_text(file_bytes, invoice_file.original_filename)
        raw_text = ocr_result["text"]

        # Template matching
        matched_template = await template_service.find_matching_template(raw_text, db)
        hints = matched_template.field_hints if matched_template else None

        # LLM parsing
        parsed = await llm_service.parse(raw_text, template_hints=hints)

        # Duplicate detection
        is_duplicate = False
        duplicate_of_id = None
        if parsed.get("invoice_number"):
            dup_result = await db.execute(
                select(Invoice).where(Invoice.invoice_number == parsed["invoice_number"])
            )
            existing = dup_result.scalar_one_or_none()
            if existing and str(existing.file_id) != file_id:
                is_duplicate = True
                duplicate_of_id = existing.id

        # Save invoice
        invoice = Invoice(
            id=uuid.uuid4(),
            file_id=file_id,
            invoice_number=parsed.get("invoice_number"),
            vendor_name=parsed.get("vendor_name"),
            vendor_normalized=parsed.get("vendor_normalized"),
            vendor_address=parsed.get("vendor_address"),
            bill_to=parsed.get("bill_to"),
            currency=parsed.get("currency", "USD"),
            subtotal=parsed.get("subtotal", 0.0),
            tax=parsed.get("tax", 0.0),
            discount=parsed.get("discount", 0.0),
            total=parsed.get("total", 0.0),
            payment_terms=parsed.get("payment_terms"),
            confidence_score=parsed.get("confidence_score", 0.7),
            raw_ocr_text=raw_text,
            extracted_json=parsed,
            is_duplicate=is_duplicate,
            duplicate_of=duplicate_of_id,
        )

        # Parse dates safely
        for date_field in ["invoice_date", "due_date"]:
            val = parsed.get(date_field)
            if val:
                try:
                    setattr(invoice, date_field, datetime.datetime.fromisoformat(val))
                except ValueError:
                    pass

        db.add(invoice)
        await db.flush()

        # Save line items
        for item in parsed.get("line_items", []):
            li = InvoiceLineItem(
                id=uuid.uuid4(),
                invoice_id=invoice.id,
                description=item.get("description", ""),
                quantity=item.get("quantity", 1.0),
                unit_price=item.get("unit_price", 0.0),
                amount=item.get("amount", 0.0),
            )
            db.add(li)

        # Template update
        template = await template_service.create_or_update_template(
            raw_text,
            parsed.get("vendor_normalized") or parsed.get("vendor_name"),
            parsed,
            db,
            existing_template_id=matched_template.id if matched_template else None,
        )
        invoice_file.template_id = template.id
        invoice_file.status = "done"
        invoice_file.processed_at = datetime.datetime.utcnow()
        await db.commit()

    except Exception as e:
        invoice_file.status = "failed"
        await db.commit()
        print(f"Processing failed for {file_id}: {e}")
        raise


@router.post("/upload")
async def upload_invoice(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(400, f"Unsupported type: {file.content_type}")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(413, "File too large (max 20MB)")

    # Upload to Supabase Storage
    storage_result = await storage_service.upload(file_bytes, file.filename)

    # Save file metadata
    invoice_file = InvoiceFile(
        id=str(uuid.uuid4()),
        original_filename=file.filename,
        file_url=storage_result["url"],
        file_type=file.filename.rsplit(".", 1)[-1].lower(),
        file_size=len(file_bytes),
        status="pending",
    )
    db.add(invoice_file)
    await db.commit()
    await db.refresh(invoice_file)

    # Save temp for background task
    import aiofiles
    async with aiofiles.open(f"/tmp/{invoice_file.id}", "wb") as f:
        await f.write(file_bytes)

    background_tasks.add_task(process_invoice_file, str(invoice_file.id), db)

    return {
        "file_id": str(invoice_file.id),
        "status": "processing",
        "message": "Invoice uploaded and queued for extraction",
    }


@router.post("/batch")
async def batch_upload(
    background_tasks: BackgroundTasks,
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
):
    if len(files) > 20:
        raise HTTPException(400, "Max 20 files per batch")

    results = []
    for file in files:
        try:
            resp = await upload_invoice(background_tasks, file, db)
            results.append({"filename": file.filename, **resp})
        except HTTPException as e:
            results.append({"filename": file.filename, "error": e.detail})

    return {"batch_size": len(files), "results": results}


@router.get("/")
async def list_invoices(
    skip: int = 0,
    limit: int = 50,
    vendor: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Invoice).order_by(desc(Invoice.created_at)).offset(skip).limit(limit)
    if vendor:
        query = query.where(Invoice.vendor_normalized.ilike(f"%{vendor}%"))
    result = await db.execute(query)
    invoices = result.scalars().all()
    return [_invoice_to_dict(inv) for inv in invoices]


@router.get("/{invoice_id}")
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Invoice).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(404, "Invoice not found")
    return _invoice_to_dict(invoice, include_raw=True)


@router.get("/{invoice_id}/retry")
async def retry_invoice(
    invoice_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(InvoiceFile).where(InvoiceFile.id == invoice_id)
    )
    inv_file = result.scalar_one_or_none()
    if not inv_file:
        raise HTTPException(404, "File not found")

    inv_file.status = "pending"
    await db.commit()
    background_tasks.add_task(process_invoice_file, invoice_id, db)
    return {"message": "Retry queued"}


def _invoice_to_dict(invoice: Invoice, include_raw: bool = False) -> dict:
    d = {
        "id": str(invoice.id),
        "invoice_number": invoice.invoice_number,
        "vendor_name": invoice.vendor_name,
        "vendor_normalized": invoice.vendor_normalized,
        "invoice_date": invoice.invoice_date.isoformat() if invoice.invoice_date else None,
        "due_date": invoice.due_date.isoformat() if invoice.due_date else None,
        "currency": invoice.currency,
        "subtotal": invoice.subtotal,
        "tax": invoice.tax,
        "discount": invoice.discount,
        "total": invoice.total,
        "payment_terms": invoice.payment_terms,
        "confidence_score": invoice.confidence_score,
        "is_duplicate": invoice.is_duplicate,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
    }
    if include_raw:
        d["extracted_json"] = invoice.extracted_json
        d["raw_ocr_text"] = invoice.raw_ocr_text
    return d
