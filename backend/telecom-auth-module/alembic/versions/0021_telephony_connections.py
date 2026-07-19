"""telephony connections (FreePBX / Asterisk integration layer)

Hybrid topology: company_id NULL = shared platform-default connection; a row
with a company_id is that tenant's override. The AMI secret is stored encrypted
(opaque Fernet token) in ami_secret_encrypted.

Partial unique indexes enforce:
  - at most ONE platform-default connection (company_id IS NULL, not deleted),
  - per-company connection names are unique among live rows.

Revision ID: 0021
Revises: 0020
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Keep revision ids short: the alembic_version column is VARCHAR(32).
revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telephony_connections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=True,
        ),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="5038"),
        sa.Column("ami_username", sa.String(255), nullable=False),
        sa.Column("ami_secret_encrypted", sa.String(1000), nullable=False),
        sa.Column("use_tls", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(1000), nullable=True),
        sa.Column(
            "created_by", postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("metadata", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_telephony_connections_company_id", "telephony_connections", ["company_id"]
    )
    # At most one platform-default connection among live rows.
    op.execute(
        "CREATE UNIQUE INDEX uq_telephony_platform_default "
        "ON telephony_connections (md5('platform-default')) "
        "WHERE company_id IS NULL AND deleted_at IS NULL"
    )
    # Per-company connection names unique among live rows.
    op.execute(
        "CREATE UNIQUE INDEX uq_telephony_company_name "
        "ON telephony_connections (company_id, name) "
        "WHERE company_id IS NOT NULL AND deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_telephony_company_name")
    op.execute("DROP INDEX IF EXISTS uq_telephony_platform_default")
    op.drop_index("ix_telephony_connections_company_id", "telephony_connections")
    op.drop_table("telephony_connections")
