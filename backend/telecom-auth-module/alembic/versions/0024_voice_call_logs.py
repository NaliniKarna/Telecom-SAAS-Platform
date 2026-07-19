"""voice_call_logs table — Call Detail Records (Voice Platform Phase 5, Step 2/2)

Creates the CDR table that backs call history, active-call monitoring, and
voice analytics.  Indexes are tuned for the three main access patterns:

  - Company-scoped history with status/direction filters (company_id, status,
    direction, started_at).
  - Active-call query (ended_at IS NULL + status IN (...)).
  - AMI event correlation (action_id lookup).

No soft-delete column: CDRs are historical records and must not be erased.

Revision ID: 0024
Revises: 0023
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "voice_call_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "connection_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("telephony_connections.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="initiated"),
        sa.Column("caller_number", sa.String(80), nullable=False),
        sa.Column("callee_number", sa.String(80), nullable=False),
        sa.Column(
            "caller_extension_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_extensions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "callee_extension_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("voice_extensions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("answered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("ring_duration_seconds", sa.Integer(), nullable=True),
        sa.Column("action_id", sa.String(100), nullable=True),
        sa.Column("context", sa.String(100), nullable=True),
        sa.Column("hangup_cause", sa.String(100), nullable=True),
        sa.Column("recording_url", sa.String(500), nullable=True),
        sa.Column(
            "initiated_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
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

    # --- Indexes ---
    # Primary CDR lookup: company-scoped history ordered by time.
    op.create_index(
        "ix_voice_call_logs_company_id", "voice_call_logs", ["company_id"]
    )
    # Filter by status (active-call view uses status + ended_at).
    op.create_index(
        "ix_voice_call_logs_status", "voice_call_logs", ["status"]
    )
    # Active-call detection: ended_at IS NULL rows are the open calls.
    op.create_index(
        "ix_voice_call_logs_ended_at", "voice_call_logs", ["ended_at"]
    )
    # AMI event correlation (action_id is unique per originate attempt).
    op.create_index(
        "ix_voice_call_logs_action_id", "voice_call_logs", ["action_id"]
    )
    # FK lookup: which calls involved this extension?
    op.create_index(
        "ix_voice_call_logs_caller_ext",
        "voice_call_logs",
        ["caller_extension_id"],
    )
    # Compound: analytics time-bucketing (company + time window).
    op.create_index(
        "ix_voice_call_logs_company_started",
        "voice_call_logs",
        ["company_id", "started_at"],
    )
    # Partial: fast active-call query.
    op.execute(
        "CREATE INDEX ix_voice_call_logs_active "
        "ON voice_call_logs (company_id, started_at DESC) "
        "WHERE ended_at IS NULL"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_voice_call_logs_active")
    op.drop_index("ix_voice_call_logs_company_started", "voice_call_logs")
    op.drop_index("ix_voice_call_logs_caller_ext", "voice_call_logs")
    op.drop_index("ix_voice_call_logs_action_id", "voice_call_logs")
    op.drop_index("ix_voice_call_logs_ended_at", "voice_call_logs")
    op.drop_index("ix_voice_call_logs_status", "voice_call_logs")
    op.drop_index("ix_voice_call_logs_company_id", "voice_call_logs")
    op.drop_table("voice_call_logs")
