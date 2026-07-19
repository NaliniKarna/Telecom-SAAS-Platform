"""company registration statuses (self-registration + approval)

Adds two values to the company_status enum so a publicly-registered company can
sit in PENDING_APPROVAL until a super admin approves it (-> active) or rejects it
(-> rejected). No new tables/columns — the self-registration flow reuses the
existing companies/users/roles/audit schema.

PostgreSQL 12+ allows ALTER TYPE ... ADD VALUE inside a transaction as long as
the new value isn't used in the same transaction (it isn't here). IF NOT EXISTS
makes this idempotent / safe to re-run.

Revision ID: 0022
Revises: 0021
"""
from alembic import op

# Keep revision ids short: the alembic_version column is VARCHAR(32).
revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TYPE company_status ADD VALUE IF NOT EXISTS 'pending_approval'")
    op.execute("ALTER TYPE company_status ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # PostgreSQL cannot drop a value from an enum type without recreating the
    # type and rewriting every dependent column. Removing these values is not
    # safe to automate, so downgrade is intentionally a no-op. (Rows using the
    # new statuses would block any type recreation anyway.)
    pass
