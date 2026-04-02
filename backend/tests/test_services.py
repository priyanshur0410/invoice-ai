"""
Unit tests for core services
Run: pytest tests/ -v
"""
import pytest
import json
from unittest.mock import AsyncMock, patch
from services.llm_service import LLMParsingService
from services.template_service import TemplateService

# ─── LLM Service Tests ───────────────────────────────────────────────────────

class TestLLMService:
    def setup_method(self):
        self.svc = LLMParsingService()

    def test_safe_parse_json_clean(self):
        raw = '{"invoice_number": "INV-001", "total": 1500.0, "currency": "USD", "confidence_score": 0.9, "line_items": []}'
        result = self.svc._safe_parse_json(raw)
        assert result["invoice_number"] == "INV-001"
        assert result["total"] == 1500.0

    def test_safe_parse_json_strips_markdown(self):
        raw = '```json\n{"total": 200.0, "currency": "EUR", "confidence_score": 0.8, "line_items": []}\n```'
        result = self.svc._safe_parse_json(raw)
        assert result["total"] == 200.0
        assert result["currency"] == "EUR"

    def test_validate_coerce_float_fields(self):
        data = {
            "subtotal": "1,500.00",
            "tax": None,
            "discount": "",
            "total": "2000",
            "currency": "usd",
            "confidence_score": 1.5,  # should be clamped to 1.0
            "line_items": [],
        }
        result = self.svc._validate_and_coerce(data)
        assert result["subtotal"] == 0.0  # "1,500.00" fails float conversion → 0.0
        assert result["tax"] == 0.0
        assert result["currency"] == "USD"
        assert result["confidence_score"] == 1.0

    def test_validate_recomputes_total_from_line_items(self):
        data = {
            "subtotal": 0.0, "tax": 0.0, "discount": 0.0, "total": 0.0,
            "currency": "USD", "confidence_score": 0.7,
            "line_items": [
                {"description": "Item A", "quantity": 2.0, "unit_price": 100.0, "amount": 200.0},
                {"description": "Item B", "quantity": 1.0, "unit_price": 50.0, "amount": 50.0},
            ]
        }
        result = self.svc._validate_and_coerce(data)
        assert result["total"] == 250.0

    def test_regex_fallback_extracts_total(self):
        text = "Invoice #: TC-001\nTotal Amount Due: $6,622.75\nDate: 2024-03-15"
        result = self.svc._regex_fallback(text)
        assert result["total"] == 6622.75
        assert result["confidence_score"] == 0.25

    def test_regex_fallback_extracts_invoice_number(self):
        text = "Invoice # TC-2024-0891\nSubtotal: $100"
        result = self.svc._regex_fallback(text)
        assert result["invoice_number"] == "TC-2024-0891"

    def test_build_user_message_with_hints(self):
        hints = {"total": "Found near: total"}
        msg = self.svc._build_user_message("some ocr text", hints)
        assert "FORMAT HINTS" in msg
        assert "some ocr text" in msg

    def test_build_user_message_truncates_long_text(self):
        long_text = "x" * 10000
        msg = self.svc._build_user_message(long_text, None)
        assert len(msg) < 7000  # truncated at 6000 chars + wrapper


# ─── Template Service Tests ───────────────────────────────────────────────────

class TestTemplateService:
    def setup_method(self):
        self.svc = TemplateService()

    def test_fingerprint_is_json(self):
        text = "Invoice\nTotal: $500\nSubtotal: $450\nTax: $50"
        fp = self.svc.compute_fingerprint(text)
        parsed = json.loads(fp)
        assert "kw" in parsed
        assert "lc" in parsed
        assert "hh" in parsed

    def test_fingerprint_detects_keywords(self):
        text = "TAX INVOICE\nGSTIN: 29AABCI1681G1ZN\nHSN: 998314"
        fp = json.loads(self.svc.compute_fingerprint(text))
        assert fp["kw"]["tax invoice"] == 1
        assert fp["kw"]["hsn"] == 1
        assert fp["kw"]["gstin"] == 1

    def test_identical_text_gives_similarity_1(self):
        text = "Invoice\nVendor: TechCorp\nTotal: $1000\nSubtotal: $900\nTax: $100"
        fp = self.svc.compute_fingerprint(text)
        assert self.svc.similarity(fp, fp) == 1.0

    def test_completely_different_text_gives_low_similarity(self):
        fp1 = self.svc.compute_fingerprint("Invoice\nTotal: $500\nSubtotal: $450")
        fp2 = self.svc.compute_fingerprint("RANDOM GROCERY RECEIPT\nApples: $2\nBread: $3")
        score = self.svc.similarity(fp1, fp2)
        assert score < 0.6

    def test_similar_invoices_give_high_similarity(self):
        text1 = "TECHCORP INVOICE\nInvoice Number: TC-001\nTotal: $1000\nSubtotal: $900\nTax: $100\nPayment terms: Net 30"
        text2 = "TECHCORP INVOICE\nInvoice Number: TC-002\nTotal: $2000\nSubtotal: $1800\nTax: $200\nPayment terms: Net 30"
        fp1 = self.svc.compute_fingerprint(text1)
        fp2 = self.svc.compute_fingerprint(text2)
        score = self.svc.similarity(fp1, fp2)
        assert score >= 0.7  # same format, same vendor

    def test_invalid_fingerprint_returns_zero(self):
        score = self.svc.similarity("{invalid", "{also invalid")
        assert score == 0.0


# ─── Integration-style test (mocked LLM) ─────────────────────────────────────

@pytest.mark.asyncio
async def test_llm_parse_uses_regex_fallback_on_error():
    svc = LLMParsingService()
    text = "Invoice #: FALLBACK-001\nTotal Amount: $999.99\nDate: 2024-01-01"

    with patch.object(svc, '_call_llm', new_callable=AsyncMock, side_effect=Exception("API down")):
        result = await svc.parse(text)

    # Should fall back to regex
    assert result["confidence_score"] == 0.25
    assert result["total"] == 999.99


@pytest.mark.asyncio
async def test_llm_parse_returns_structured_data():
    svc = LLMParsingService()
    mock_response = {
        "invoice_number": "INV-2024-001",
        "vendor_name": "TechCorp Solutions Inc.",
        "vendor_normalized": "TechCorp",
        "vendor_address": "123 Silicon Valley Blvd",
        "bill_to": "Acme Corp",
        "invoice_date": "2024-03-15",
        "due_date": "2024-04-14",
        "currency": "USD",
        "subtotal": 6150.00,
        "tax": 522.75,
        "discount": 50.00,
        "total": 6622.75,
        "payment_terms": "Net 30",
        "line_items": [
            {"description": "Cloud Services", "quantity": 1, "unit_price": 2500, "amount": 2500}
        ],
        "confidence_score": 0.95,
    }

    with patch.object(svc, '_call_llm', new_callable=AsyncMock, return_value=mock_response):
        result = await svc.parse("some ocr text")

    assert result["invoice_number"] == "INV-2024-001"
    assert result["total"] == 6622.75
    assert result["confidence_score"] == 0.95
    assert len(result["line_items"]) == 1
