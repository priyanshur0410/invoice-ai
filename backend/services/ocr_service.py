"""
OCR Service
- Handles PDF (pdfplumber for text-PDFs, pytesseract for scanned)
- Handles JPG/PNG via pytesseract
- Returns raw text + page count
"""
import io
import base64
from pathlib import Path
import pytesseract
from PIL import Image
import pdfplumber
import fitz  # PyMuPDF


class OCRService:

    SUPPORTED_TYPES = {"pdf", "jpg", "jpeg", "png"}

    async def extract_text(self, file_bytes: bytes, filename: str) -> dict:
        ext = Path(filename).suffix.lower().lstrip(".")
        if ext not in self.SUPPORTED_TYPES:
            raise ValueError(f"Unsupported file type: {ext}")

        if ext == "pdf":
            return await self._process_pdf(file_bytes)
        else:
            return await self._process_image(file_bytes)

    async def _process_pdf(self, file_bytes: bytes) -> dict:
        pages_text = []
        total_chars = 0

        # Try pdfplumber first (fast, accurate for text PDFs)
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ""
                pages_text.append(text.strip())
                total_chars += len(text.strip())

        # If text-based PDF had very little content, it's likely scanned → use OCR
        if total_chars < 100:
            pages_text = await self._ocr_pdf_pages(file_bytes)

        return {
            "text": "\n\n--- PAGE BREAK ---\n\n".join(pages_text),
            "pages": len(pages_text),
            "method": "pdfplumber" if total_chars >= 100 else "tesseract_pdf",
        }

    async def _ocr_pdf_pages(self, file_bytes: bytes) -> list[str]:
        """Render each PDF page as image and OCR it."""
        pages_text = []
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page_num in range(len(doc)):
            page = doc[page_num]
            mat = fitz.Matrix(2.0, 2.0)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            img_bytes = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_bytes))
            text = pytesseract.image_to_string(img, config="--psm 6")
            pages_text.append(text.strip())
        return pages_text

    async def _process_image(self, file_bytes: bytes) -> dict:
        img = Image.open(io.BytesIO(file_bytes))
        # Pre-process: convert to grayscale, increase contrast
        img = img.convert("L")
        text = pytesseract.image_to_string(img, config="--psm 6 --oem 3")
        return {
            "text": text.strip(),
            "pages": 1,
            "method": "tesseract_image",
        }

    def get_confidence(self, file_bytes: bytes) -> float:
        """Returns per-word confidence from Tesseract for images."""
        try:
            img = Image.open(io.BytesIO(file_bytes)).convert("L")
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            scores = [int(c) for c in data["conf"] if str(c).isdigit() and int(c) >= 0]
            return round(sum(scores) / len(scores) / 100, 2) if scores else 0.5
        except Exception:
            return 0.5


ocr_service = OCRService()
