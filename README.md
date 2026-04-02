# ⚡ Invoice Extraction AI

An AI-powered application that extracts structured data from invoice documents, stores results in Supabase, and provides analytics on extracted data.

---

## 🏗️ System Architecture

```
┌──────────────────────────────────────────────────────────┐
│                        Frontend (React)                   │
│   Upload Page → Invoice List → Analytics Dashboard        │
└──────────────────────────┬───────────────────────────────┘
                           │ HTTP/REST
┌──────────────────────────▼───────────────────────────────┐
│                  Backend (FastAPI)                        │
│                                                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │  /upload │  │/invoices │  │    /analytics         │   │
│  └────┬─────┘  └──────────┘  └──────────────────────┘   │
│       │                                                   │
│  ┌────▼──────────────────────────────────────────────┐   │
│  │              Processing Pipeline                   │   │
│  │                                                    │   │
│  │  File Upload → OCR → Template Match → LLM Parse  │   │
│  │      ↓           ↓           ↓            ↓       │   │
│  │  Supabase   Tesseract/  Fingerprint    GPT-4o     │   │
│  │  Storage    pdfplumber   Similarity   (fallback:  │   │
│  │                                      GPT-3.5 →   │   │
│  │                                      regex)       │   │
│  └──────────────────────────┬─────────────────────── ┘   │
└─────────────────────────────┼────────────────────────────┘
                              │
┌─────────────────────────────▼────────────────────────────┐
│                    Supabase                               │
│                                                           │
│  PostgreSQL DB          Storage Bucket                    │
│  ├── users              └── invoices/{user_id}/{hash}.ext │
│  ├── invoice_files                                        │
│  ├── invoices                                             │
│  ├── invoice_line_items                                   │
│  └── invoice_templates                                    │
└──────────────────────────────────────────────────────────┘
```

---

## 🗄️ Database Design

### Tables

| Table | Purpose |
|---|---|
| `users` | Auth & ownership |
| `invoice_files` | File metadata + Supabase Storage URL |
| `invoices` | Extracted structured data |
| `invoice_line_items` | Per-line-item rows from each invoice |
| `invoice_templates` | Layout fingerprints for format reuse |

### Key Design Decisions

**Separation of `invoice_files` and `invoices`:**
- `invoice_files` tracks the upload + processing lifecycle (status, file_url, timestamps)
- `invoices` holds pure business data (vendor, total, line items)
- Allows retrying extraction without re-uploading files

**`invoice_templates` table (Format Reuse):**
- Stores a JSON "fingerprint" of each invoice format (keyword presence vector + header hash)
- Similarity computed via Jaccard score on keyword presence
- On 80%+ match, field hints are passed to LLM → faster + more accurate parsing
- `success_rate` updated via EMA after each extraction → learning system

**`vendor_normalized` column:**
- Raw vendor names can be noisy ("AMAZON.COM INC", "Amazon Inc.", "amazon")
- LLM normalizes to canonical form
- Analytics always group by `vendor_normalized`, not raw `vendor_name`

**`is_duplicate` + `duplicate_of` columns:**
- Detected at extraction time by matching `invoice_number`
- Soft flag (not delete) to preserve audit trail

---

## 🧠 Key Design Decisions

### 1. OCR Strategy (Two-pass)
```
PDF input
  ├─ Try pdfplumber (text-layer PDF) → fast, ~99% accurate
  └─ If < 100 chars extracted → scanned PDF → PyMuPDF render + Tesseract
Image input → Tesseract directly (grayscale pre-processing for better accuracy)
```

### 2. LLM Prompt Engineering
The system prompt enforces:
- JSON-only output (`response_format: json_object`) → eliminates markdown wrapping
- `null` for missing fields (prevents hallucination)
- ISO 8601 date format
- 0–1 `confidence_score` included in output
- Vendor normalization in the same pass (cost-efficient vs. a second LLM call)

**Template hint injection:** When a matching template is found, the prompt includes:
```json
"FORMAT HINTS (from previously seen similar invoice): { ... }"
```
This dramatically improves accuracy for repeat vendors.

### 3. Fallback Chain
```
GPT-4o → GPT-3.5-turbo → Regex heuristics
```
- GPT-4o: best quality
- GPT-3.5: cheaper, slightly lower accuracy (confidence_score reduced by 0.1)
- Regex: last resort; returns `confidence_score: 0.25`

### 4. Format Detection & Reuse
Fingerprint = JSON with:
- Binary presence vector of 20+ layout keywords ("invoice", "hsn", "gst", etc.)
- Line-count bucket (0–10)
- MD5 hash of first 5 lines (header region)

Similarity = Jaccard(keyword vectors) × 0.75 + header_match_bonus × 0.25

---

## 📊 Analytics Layer

| Endpoint | Description |
|---|---|
| `/api/analytics/summary` | Total invoices, total spend, avg confidence, vendor count |
| `/api/analytics/vendor-spend` | Spend grouped by `vendor_normalized` |
| `/api/analytics/monthly-trend` | Month-wise invoice count and spend |
| `/api/analytics/currency-totals` | Per-currency totals |
| `/api/analytics/top-vendors` | Top N vendors by spend |

All queries use SQLAlchemy `func.sum`, `func.count`, `func.extract` — efficient single-query aggregations.

---

## ⚙️ Setup & Running

### Backend
```bash
cd backend
cp .env.example .env          # fill in Supabase + OpenAI keys
pip install -r requirements.txt
sudo apt install tesseract-ocr  # for OCR
uvicorn main:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

### Environment Variables
```
DATABASE_URL=postgresql+asyncpg://...supabase.co:5432/postgres
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_SERVICE_KEY=service-role-key
SUPABASE_BUCKET=invoices
OPENAI_API_KEY=sk-...
```

---

## 🚀 Deployment

**Backend → Render**
- Build: `pip install -r requirements.txt`
- Start: `uvicorn main:app --host 0.0.0.0 --port $PORT`

**Frontend → Vercel**
- Framework: Vite
- Set `VITE_API_URL` env variable to your Render URL

---

## 🔒 Assumptions & Limitations

1. **OCR accuracy:** Tesseract struggles with very low-resolution or handwritten invoices. External OCR (Google Vision, AWS Textract) would improve this but adds cost.
2. **LLM cost:** GPT-4o is used as primary parser. For high volume, switch primary to GPT-3.5 or use a batching strategy.
3. **Currency conversion:** Analytics currently show raw totals per currency, not converted to a base currency. A forex API would be needed for cross-currency spend analysis.
4. **Authentication:** User model exists but auth middleware (Supabase Auth / JWT) is not wired in this version — all uploads are anonymous.
5. **Template similarity threshold:** 0.80 is conservative. May miss similar formats; can be tuned lower (0.70) for more aggressive reuse.

---

## 🔮 Potential Improvements

| Area | Improvement |
|---|---|
| OCR | Integrate Google Vision API for better handwriting/low-res support |
| LLM | Fine-tune a smaller model on invoice data to reduce cost 10× |
| Format Reuse | Use embedding similarity (text-embedding-3-small) instead of keyword Jaccard |
| Auth | Add Supabase Auth with Row-Level Security on all tables |
| Webhooks | Notify user via email/Slack when batch processing completes |
| Confidence | Per-field confidence scores, not just overall |
| Field Highlighting | Return bounding box coordinates from OCR for UI highlighting |
| Forex | Integrate Open Exchange Rates for unified currency analytics |
| Queue | Replace BackgroundTasks with Celery + Redis for production-scale batch jobs |
| Vendor DB | Match vendor names against a reference database (Dun & Bradstreet, OpenCorporates) |

---

## 🎯 Bonus Features Implemented

- ✅ Batch upload (up to 20 files)
- ✅ Confidence score per invoice
- ✅ Retry logic (GPT-4o → GPT-3.5 → regex fallback)
- ✅ Vendor normalization
- ✅ Duplicate detection
- ✅ Format reuse with learning system (template success_rate EMA)
- ✅ Analytics dashboard

---

## 📁 Project Structure

```
invoice-ai/
├── backend/
│   ├── main.py                    # FastAPI app entry point
│   ├── requirements.txt
│   ├── .env.example
│   ├── models/
│   │   └── database.py            # SQLAlchemy models + Supabase schema
│   ├── routers/
│   │   ├── invoices.py            # Upload, list, detail, retry endpoints
│   │   ├── analytics.py           # Spend, trend, currency endpoints
│   │   └── files.py               # File metadata endpoints
│   └── services/
│       ├── ocr_service.py         # Tesseract + pdfplumber OCR
│       ├── llm_service.py         # GPT-4o parsing with fallback chain
│       ├── template_service.py    # Format fingerprinting & reuse
│       └── storage_service.py     # Supabase Storage upload
└── frontend/
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── App.jsx                # Root + navigation
        ├── App.css                # Global styles
        └── pages/
            ├── UploadPage.jsx     # Drag-drop upload + queue
            ├── InvoicesPage.jsx   # Invoice table + detail view
            └── AnalyticsPage.jsx  # Dashboard charts
```
