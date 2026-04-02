"""Initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
import uuid

revision = '001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('email', sa.String(255), unique=True, nullable=False),
        sa.Column('name', sa.String(255)),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'invoice_templates',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column('name', sa.String(300)),
        sa.Column('vendor_hint', sa.String(500)),
        sa.Column('layout_fingerprint', sa.Text),
        sa.Column('field_hints', sa.JSON),
        sa.Column('sample_count', sa.Integer, server_default='1'),
        sa.Column('success_rate', sa.Float, server_default='1.0'),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'invoice_files',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('original_filename', sa.String(500), nullable=False),
        sa.Column('file_url', sa.Text, nullable=False),
        sa.Column('file_type', sa.String(20)),
        sa.Column('file_size', sa.Integer),
        sa.Column('status', sa.String(30), server_default='pending'),
        sa.Column('template_id', UUID(as_uuid=True), sa.ForeignKey('invoice_templates.id'), nullable=True),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime, nullable=True),
    )

    op.create_table(
        'invoices',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('file_id', UUID(as_uuid=True), sa.ForeignKey('invoice_files.id'), unique=True),
        sa.Column('invoice_number', sa.String(200)),
        sa.Column('vendor_name', sa.String(500)),
        sa.Column('vendor_normalized', sa.String(500)),
        sa.Column('vendor_address', sa.Text),
        sa.Column('bill_to', sa.Text),
        sa.Column('invoice_date', sa.DateTime, nullable=True),
        sa.Column('due_date', sa.DateTime, nullable=True),
        sa.Column('currency', sa.String(10), server_default='USD'),
        sa.Column('subtotal', sa.Float, server_default='0'),
        sa.Column('tax', sa.Float, server_default='0'),
        sa.Column('discount', sa.Float, server_default='0'),
        sa.Column('total', sa.Float, server_default='0'),
        sa.Column('payment_terms', sa.String(200)),
        sa.Column('is_duplicate', sa.Boolean, server_default='false'),
        sa.Column('duplicate_of', UUID(as_uuid=True), sa.ForeignKey('invoices.id'), nullable=True),
        sa.Column('confidence_score', sa.Float, server_default='0'),
        sa.Column('raw_ocr_text', sa.Text),
        sa.Column('extracted_json', sa.JSON),
        sa.Column('created_at', sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        'invoice_line_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('invoice_id', UUID(as_uuid=True), sa.ForeignKey('invoices.id')),
        sa.Column('description', sa.Text),
        sa.Column('quantity', sa.Float, server_default='1'),
        sa.Column('unit_price', sa.Float, server_default='0'),
        sa.Column('amount', sa.Float, server_default='0'),
    )

    # Indexes for analytics queries
    op.create_index('idx_invoices_vendor', 'invoices', ['vendor_normalized'])
    op.create_index('idx_invoices_date', 'invoices', ['invoice_date'])
    op.create_index('idx_invoices_currency', 'invoices', ['currency'])
    op.create_index('idx_invoice_files_status', 'invoice_files', ['status'])


def downgrade():
    op.drop_table('invoice_line_items')
    op.drop_table('invoices')
    op.drop_table('invoice_files')
    op.drop_table('invoice_templates')
    op.drop_table('users')
