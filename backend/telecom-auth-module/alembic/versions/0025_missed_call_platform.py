"""missed call platform tables (Phase 6)

Creates three tables:
  missed_calls          — master missed-call log (company-scoped)
  missed_call_notes     — append-only notes per missed call
  missed_call_callbacks — callback attempt records

Indexes optimised for:
  - Company-scoped list + filter by status/date
  - Active missed calls (status = 'new')
  - Assignment lookup
  - Callback history per missed call

Revision ID: 0025
Revises: 0024
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── missed_calls ─────────────────────────────────────────────────────────
    op.create_table(
        "missed_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("caller_number", sa.String(80), nullable=False),
        sa.Column("called_number", sa.String(80), nullable=False),
        sa.Column(
            "called_extension_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_extensions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(20),
            nullable=False,
            server_default="new",
        ),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ring_duration_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "source_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_call_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "assigned_to",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "callback_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column("caller_name", sa.String(255), nullable=True),
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
    )
    op.create_index("ix_missed_calls_company_id", "missed_calls", ["company_id"])
    op.create_index("ix_missed_calls_status", "missed_calls", ["status"])
    op.create_index(
        "ix_missed_calls_called_ext", "missed_calls", ["called_extension_id"]
    )
    op.create_index("ix_missed_calls_assigned_to", "missed_calls", ["assigned_to"])
    op.create_index(
        "ix_missed_calls_company_received",
        "missed_calls",
        ["company_id", "received_at"],
    )
    # Partial: fast "new missed calls" lookup for dashboard badge.
    op.execute(
        "CREATE INDEX ix_missed_calls_new "
        "ON missed_calls (company_id, received_at DESC) "
        "WHERE status = 'new'"
    )

    # ── missed_call_notes ────────────────────────────────────────────────────
    op.create_table(
        "missed_call_notes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "missed_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missed_calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "author_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column("body", sa.Text(), nullable=False),
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
    )
    op.create_index(
        "ix_missed_call_notes_mc_id", "missed_call_notes", ["missed_call_id"]
    )

    # ── missed_call_callbacks ────────────────────────────────────────────────
    op.create_table(
        "missed_call_callbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "missed_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("missed_calls.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "performed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=False,
        ),
        sa.Column(
            "extension_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_extensions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "voice_call_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_call_logs.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
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
    )
    op.create_index(
        "ix_missed_call_callbacks_mc_id",
        "missed_call_callbacks",
        ["missed_call_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_missed_call_callbacks_mc_id", "missed_call_callbacks")
    op.drop_table("missed_call_callbacks")
    op.drop_index("ix_missed_call_notes_mc_id", "missed_call_notes")
    op.drop_table("missed_call_notes")
    op.execute("DROP INDEX IF EXISTS ix_missed_calls_new")
    op.drop_index("ix_missed_calls_company_received", "missed_calls")
    op.drop_index("ix_missed_calls_assigned_to", "missed_calls")
    op.drop_index("ix_missed_calls_called_ext", "missed_calls")
    op.drop_index("ix_missed_calls_status", "missed_calls")
    op.drop_index("ix_missed_calls_company_id", "missed_calls")
    op.drop_table("missed_calls")
