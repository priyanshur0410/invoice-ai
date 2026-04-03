"""
LLM Parsing Service
- Converts raw OCR text → structured invoice JSON
- Uses OpenAI GPT-4o with carefully engineered prompts
- Includes fallback chain: GPT-4o → GPT-3.5 → regex heuristics
- Template-aware: if a known format is detected, injects field hints
"""
import json
import re
import os
from typing import Optional
from openai import AsyncOpenAI
from services.llm_service import LLMParsingService

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))


SYSTEM_PROMPT = """You are an expert invoice parser. Extract structured data from raw OCR text.

RULES:
1. Return ONLY valid JSON, no markdown, no explanation.
2. Use null for missing fields — never guess or hallucinate values.
3. All amounts must be floating-point numbers (e.g. 1250.00).
4. Dates must be ISO 8601 format: YYYY-MM-DD. If year is missing, assume current year.
5. Currency: use 3-letter ISO code (USD, EUR, INR, GBP, etc.). Default USD.
6. line_items: extract every individual product/service row.
7. confidence_score: your 0.0–1.0 confidence in the extraction quality.
8. vendor_normalized: clean, canonical vendor name (remove Inc/Ltd/LLC suffixes noise).

OUTPUT SCHEMA:
{
  "invoice_number": "string or null",
  "vendor_name": "string or null",
  "vendor_normalized": "string or null",
  "vendor_address": "string or null",
  "bill_to": "string or null",
  "invoice_date": "YYYY-MM-DD or null",
  "due_date": "YYYY-MM-DD or null",
  "currency": "USD",
  "subtotal": 0.00,
  "tax": 0.00,
  "discount": 0.00,
  "total": 0.00,
  "payment_terms": "string or null",
  "line_items": [
    {
      "description": "string",
      "quantity": 1.0,
      "unit_price": 0.00,
      "amount": 0.00
    }
  ],
  "confidence_score": 0.85
}"""


FALLBACK_PROMPT = """Extract invoice data from this text. Return ONLY JSON matching this schema exactly.
If a field is not found, use null. Do not add extra fields."""


class LLMParsingService:

    async def parse(
        self,
        ocr_text: str,
        template_hints: Optional[dict] = None,
    ) -> dict:
        """
        Main entry: try GPT-4o → GPT-3.5 fallback → regex heuristics fallback.
        Returns parsed dict with confidence_score.
        """
        user_msg = self._build_user_message(ocr_text, template_hints)

        # Attempt 1: GPT-4o (best quality)
        try:
            result = await self._call_llm("gpt-4o", user_msg, SYSTEM_PROMPT)
            if result:
                return result
        except Exception as e:
            print(f"GPT-4o failed: {e}")

        # Attempt 2: GPT-3.5 (cheaper fallback)
        try:
            result = await self._call_llm("gpt-3.5-turbo", user_msg, FALLBACK_PROMPT)
            if result:
                result["confidence_score"] = max(0.0, result.get("confidence_score", 0.5) - 0.1)
                return result
        except Exception as e:
            print(f"GPT-3.5 failed: {e}")

        # Attempt 3: Regex heuristics (last resort)
        return self._regex_fallback(ocr_text)

    def _build_user_message(self, ocr_text: str, hints: Optional[dict]) -> str:
        msg = f"OCR TEXT:\n```\n{ocr_text[:6000]}\n```"
        if hints:
            msg += f"\n\nFORMAT HINTS (from previously seen similar invoice):\n{json.dumps(hints, indent=2)}"
        return msg

    async def _call_llm(self, model: str, user_msg: str, system: str) -> Optional[dict]:
        resp = await client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.1,
            max_tokens=1500,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        return self._safe_parse_json(raw)

    def _safe_parse_json(self, text: str) -> Optional[dict]:
        """Strip markdown fences if present, then parse JSON."""
        text = re.sub(r"```json|```", "", text).strip()
        try:
            data = json.loads(text)
            return self._validate_and_coerce(data)
        except json.JSONDecodeError:
            return None

    def _validate_and_coerce(self, data: dict) -> dict:
        """Ensure correct types and fill defaults."""
        float_fields = ["subtotal", "tax", "discount", "total"]
        for f in float_fields:
            try:
                data[f] = float(data.get(f) or 0.0)
            except (ValueError, TypeError):
                data[f] = 0.0

        data["confidence_score"] = min(1.0, max(0.0, float(data.get("confidence_score", 0.7))))
        data["currency"] = (data.get("currency") or "USD").upper()[:3]

        # Validate line items
        items = data.get("line_items") or []
        cleaned = []
        for item in items:
            if isinstance(item, dict):
                cleaned.append({
                    "description": str(item.get("description") or ""),
                    "quantity": float(item.get("quantity") or 1.0),
                    "unit_price": float(item.get("unit_price") or 0.0),
                    "amount": float(item.get("amount") or 0.0),
                })
        data["line_items"] = cleaned

        # Sanity: if total == 0 but line items exist, recompute
        if data["total"] == 0.0 and cleaned:
            data["total"] = round(sum(i["amount"] for i in cleaned), 2)

        return data

    def _regex_fallback(self, text: str) -> dict:
        """Bare-minimum regex extraction when LLM is unavailable."""
        def find(patterns: list[str]) -> Optional[str]:
            for p in patterns:
                m = re.search(p, text, re.IGNORECASE)
                if m:
                    return m.group(1).strip()
            return None

        total = find([
            r"total[:\s]+[\$£€]?\s*([\d,]+\.?\d*)",
            r"amount due[:\s]+[\$£€]?\s*([\d,]+\.?\d*)",
            r"grand total[:\s]+[\$£€]?\s*([\d,]+\.?\d*)",
        ])

        return {
            "invoice_number": find([r"invoice\s*#?\s*:?\s*([A-Z0-9\-\/]+)", r"inv[:\s]+([A-Z0-9\-]+)"]),
            "vendor_name": find([r"from[:\s]+(.+?)(?:\n|bill)", r"^([A-Z][A-Za-z\s,]+(?:Inc|Ltd|LLC|Co)\.?)"]),
            "vendor_normalized": None,
            "vendor_address": None,
            "bill_to": None,
            "invoice_date": find([r"date[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})", r"(\d{4}-\d{2}-\d{2})"]),
            "due_date": find([r"due\s*date[:\s]+(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})"]),
            "currency": "USD",
            "subtotal": 0.0,
            "tax": 0.0,
            "discount": 0.0,
            "total": float(total.replace(",", "")) if total else 0.0,
            "payment_terms": find([r"(net\s*\d+|due on receipt|immediate)", r"terms[:\s]+(.+?)(?:\n|$)"]),
            "line_items": [],
            "confidence_score": 0.25,  # low — regex only
        }


llm_service = LLMParsingService()
