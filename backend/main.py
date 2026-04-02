from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn
from routers import invoices, analytics, files
from models.database import init_db

app = FastAPI(
    title="Invoice Extraction AI",
    description="AI-powered invoice data extraction with analytics",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router, prefix="/api/invoices", tags=["invoices"])
app.include_router(analytics.router, prefix="/api/analytics", tags=["analytics"])
app.include_router(files.router, prefix="/api/files", tags=["files"])

@app.on_event("startup")
async def startup():
    await init_db()

@app.get("/health")
async def health():
    return {"status": "ok", "service": "Invoice Extraction AI"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
