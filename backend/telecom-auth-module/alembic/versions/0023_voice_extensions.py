"""voice_extensions table (Voice Platform Phase 5 — Step 1/2)

Creates the per-company extension registry.  Extension numbers are unique per
company among live (non-deleted) rows, enforced by a partial unique index.

Revision ID: 0023
Revises: 0022
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# Short revision IDs — VARCHAR(32) alembic_version column constraint.
revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_extensions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extension_number", sa.String(20), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column(
            "context", sa.String(100), nullable=False, server_default="from-internal"
        ),
        sa.Column(
            "technology", sa.String(20), nullable=False, server_default="PJSIP"
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "agent_status", sa.String(20), nullable=False, server_default="offline"
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Indexes on lookup-hot columns.
    op.create_index(
        "ix_voice_extensions_company_id", "voice_extensions", ["company_id"]
    )
    op.create_index(
        "ix_voice_extensions_user_id", "voice_extensions", ["user_id"]
    )

    # Partial unique: extension numbers unique per company among live rows only.
    # Soft-deleted extensions do NOT block reuse of the same number.
    op.execute(
        "CREATE UNIQUE INDEX uq_voice_ext_company_number "
        "ON voice_extensions (company_id, extension_number) "
        "WHERE deleted_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_voice_ext_company_number")
    op.drop_index("ix_voice_extensions_user_id", "voice_extensions")
    op.drop_index("ix_voice_extensions_company_id", "voice_extensions")
    op.drop_table("voice_extensions")
