"""
Template Service
- Detects invoice format by computing a layout fingerprint from OCR text
- Matches against stored templates (fuzzy keyword similarity)
- On match: returns field hints to LLM for better accuracy
- On new format: creates new template entry
- Updates template success_rate over time (learning system)
"""
import hashlib
import json
import re
from difflib import SequenceMatcher
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from models.database import InvoiceTemplate
import uuid
import datetime


# Keywords that identify invoice format/layout
LAYOUT_KEYWORDS = [
    "invoice", "bill", "receipt", "tax invoice", "proforma",
    "purchase order", "statement", "remittance",
    "subtotal", "total", "amount due", "balance due",
    "payment terms", "net 30", "net 60", "due date",
    "item", "description", "qty", "quantity", "unit price",
    "hsn", "gstin", "vat", "gst",  # India-specific
]


class TemplateService:

    def compute_fingerprint(self, ocr_text: str) -> str:
        """
        Creates a layout fingerprint:
        - Which layout keywords are present (binary presence vector)
        - Rough line-count and density bucket
        Returns a JSON string for storage + comparison.
        """
        text_lower = ocr_text.lower()
        keyword_presence = {kw: int(kw in text_lower) for kw in LAYOUT_KEYWORDS}

        lines = [l.strip() for l in ocr_text.split("\n") if l.strip()]
        line_count_bucket = min(len(lines) // 10, 10)  # bucket 0-10

        # Header block: first 5 non-empty lines (vendor fingerprint region)
        header_block = " ".join(lines[:5]).lower()
        header_hash = hashlib.md5(header_block.encode()).hexdigest()[:8]

        return json.dumps({
            "kw": keyword_presence,
            "lc": line_count_bucket,
            "hh": header_hash,
        }, separators=(",", ":"))

    def similarity(self, fp1: str, fp2: str) -> float:
        """Returns 0.0-1.0 similarity between two fingerprints."""
        try:
            d1, d2 = json.loads(fp1), json.loads(fp2)
            kw1, kw2 = d1.get("kw", {}), d2.get("kw", {})

            # Jaccard on keyword presence
            keys = set(kw1) | set(kw2)
            matches = sum(kw1.get(k, 0) == kw2.get(k, 0) for k in keys)
            kw_sim = matches / len(keys) if keys else 0

            # Header hash exact match bonus
            hh_bonus = 0.25 if d1.get("hh") == d2.get("hh") else 0

            return min(1.0, kw_sim * 0.75 + hh_bonus)
        except Exception:
            return 0.0

    async def find_matching_template(
        self, ocr_text: str, db: AsyncSession, threshold: float = 0.80
    ) -> Optional[InvoiceTemplate]:
        fingerprint = self.compute_fingerprint(ocr_text)
        result = await db.execute(select(InvoiceTemplate))
        templates = result.scalars().all()

        best_match, best_score = None, 0.0
        for tmpl in templates:
            score = self.similarity(fingerprint, tmpl.layout_fingerprint or "{}")
            if score > best_score:
                best_score, best_match = score, tmpl

        if best_score >= threshold:
            return best_match
        return None

    async def create_or_update_template(
        self,
        ocr_text: str,
        vendor_name: Optional[str],
        extracted_data: dict,
        db: AsyncSession,
        existing_template_id=None,
    ) -> InvoiceTemplate:
        fingerprint = self.compute_fingerprint(ocr_text)

        # Build field hints from successfully extracted fields
        field_hints = {}
        for field in ["invoice_number", "invoice_date", "due_date", "total", "currency"]:
            if extracted_data.get(field):
                field_hints[field] = f"Found near: {field.replace('_', ' ')}"

        if existing_template_id:
            # Update success count
            await db.execute(
                update(InvoiceTemplate)
                .where(InvoiceTemplate.id == existing_template_id)
                .values(
                    sample_count=InvoiceTemplate.sample_count + 1,
                    updated_at=datetime.datetime.utcnow(),
                    field_hints=field_hints,
                )
            )
            await db.commit()
            result = await db.execute(
                select(InvoiceTemplate).where(InvoiceTemplate.id == existing_template_id)
            )
            return result.scalar_one()
        else:
            template = InvoiceTemplate(
                id=uuid.uuid4(),
                name=f"{vendor_name or 'Unknown'} Template",
                vendor_hint=vendor_name,
                layout_fingerprint=fingerprint,
                field_hints=field_hints,
            )
            db.add(template)
            await db.commit()
            await db.refresh(template)
            return template

    async def update_success_rate(
        self, template_id, success: bool, db: AsyncSession
    ):
        """Called after human review or confidence threshold check."""
        result = await db.execute(
            select(InvoiceTemplate).where(InvoiceTemplate.id == template_id)
        )
        tmpl = result.scalar_one_or_none()
        if tmpl:
            # Exponential moving average
            old_rate = tmpl.success_rate or 1.0
            new_rate = old_rate * 0.9 + (1.0 if success else 0.0) * 0.1
            await db.execute(
                update(InvoiceTemplate)
                .where(InvoiceTemplate.id == template_id)
                .values(success_rate=new_rate)
            )
            await db.commit()


template_service = TemplateService()
