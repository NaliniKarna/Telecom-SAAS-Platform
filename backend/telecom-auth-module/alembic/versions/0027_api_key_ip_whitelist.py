"""add ip_whitelist to api_keys

Adds an optional list of allowed IPs/CIDR ranges per API key. Null/empty
means "allow any IP" (backward compatible with existing keys). Enforcement
point is the future request-authentication scheme (see api_key_service.
is_ip_allowed) — this migration only adds the column and storage.

Revision ID: 0027
Revises: 0026
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "api_keys",
        sa.Column(
            "ip_whitelist",
            postgresql.ARRAY(sa.String(64)),
            nullable=True,
            server_default=None,
            comment="Allowed IPs/CIDR ranges. Null/empty = allow any IP.",
        ),
    )


def downgrade() -> None:
    op.drop_column("api_keys", "ip_whitelist")
