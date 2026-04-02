"""
Supabase + SQLAlchemy models for Invoice AI
Tables: users, invoice_files, invoices, invoice_line_items, invoice_templates
"""
from sqlalchemy import (
    Column, String, Float, Integer, DateTime, Boolean,
    ForeignKey, Text, JSON, Enum as SAEnum
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
import uuid
import datetime
import os

Base = declarative_base()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/invoiceai")

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    invoice_files = relationship("InvoiceFile", back_populates="user")


class InvoiceFile(Base):
    __tablename__ = "invoice_files"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    original_filename = Column(String(500), nullable=False)
    file_url = Column(Text, nullable=False)           # Supabase Storage URL
    file_type = Column(String(20))                    # pdf, jpg, png
    file_size = Column(Integer)                       # bytes
    status = Column(String(30), default="pending")    # pending, processing, done, failed
    template_id = Column(UUID(as_uuid=True), ForeignKey("invoice_templates.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    processed_at = Column(DateTime, nullable=True)
    user = relationship("User", back_populates="invoice_files")
    invoice = relationship("Invoice", back_populates="file", uselist=False)
    template = relationship("InvoiceTemplate", back_populates="files")


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_id = Column(UUID(as_uuid=True), ForeignKey("invoice_files.id"), unique=True)
    invoice_number = Column(String(200))
    vendor_name = Column(String(500))
    vendor_normalized = Column(String(500))           # cleaned vendor name
    vendor_address = Column(Text)
    bill_to = Column(Text)
    invoice_date = Column(DateTime, nullable=True)
    due_date = Column(DateTime, nullable=True)
    currency = Column(String(10), default="USD")
    subtotal = Column(Float, default=0.0)
    tax = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    total = Column(Float, default=0.0)
    payment_terms = Column(String(200))
    is_duplicate = Column(Boolean, default=False)
    duplicate_of = Column(UUID(as_uuid=True), ForeignKey("invoices.id"), nullable=True)
    confidence_score = Column(Float, default=0.0)     # 0-1 LLM confidence
    raw_ocr_text = Column(Text)
    extracted_json = Column(JSON)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    file = relationship("InvoiceFile", back_populates="invoice")
    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    invoice_id = Column(UUID(as_uuid=True), ForeignKey("invoices.id"))
    description = Column(Text)
    quantity = Column(Float, default=1.0)
    unit_price = Column(Float, default=0.0)
    amount = Column(Float, default=0.0)
    invoice = relationship("Invoice", back_populates="line_items")


class InvoiceTemplate(Base):
    """
    Detected invoice format/layout fingerprints for format reuse.
    When a new invoice matches an existing template, we skip generic extraction
    and use the proven field-position hints → faster + more accurate.
    """
    __tablename__ = "invoice_templates"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(300))
    vendor_hint = Column(String(500))
    layout_fingerprint = Column(Text)    # JSON-serialized keyword/positional hash
    field_hints = Column(JSON)           # {field: regex/keyword_anchor}
    sample_count = Column(Integer, default=1)
    success_rate = Column(Float, default=1.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    files = relationship("InvoiceFile", back_populates="template")
