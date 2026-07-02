"""group_type internal only

Removes the CONTACT value from the group_type enum. Groups are organizational
user groups only; Contacts use their own dedicated contact_lists tables, so a
CONTACT group type no longer provides value.

The group_type COLUMN is intentionally kept (always 'internal') to avoid
restructuring the Groups module — only the enum's value set is narrowed.

Postgres cannot drop a value from an enum in place, so we rebuild the type:
create a new single-value enum, swap the column over, drop the old type, rename.
A guard first fails loudly if any group still uses 'contact' (convert those to
'internal' before running this migration).

Revision ID: 0012_group_type_internal_only
Revises: 0011_contact_lists
"""
import sqlalchemy as sa
from alembic import op

revision = "0012_group_type_internal_only"
down_revision = "0011_contact_lists"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Guard: refuse to proceed if any group is still typed 'contact'.
    count = bind.execute(
        sa.text("SELECT count(*) FROM groups WHERE group_type = 'contact'")
    ).scalar_one()
    if count:
        raise RuntimeError(
            f"{count} group(s) still have group_type='contact'. Convert them to "
            "'internal' before running this migration: "
            "UPDATE groups SET group_type='internal' WHERE group_type='contact';"
        )

    # Rebuild the enum with only 'internal'.
    op.execute("ALTER TYPE group_type RENAME TO group_type_old")
    op.execute("CREATE TYPE group_type AS ENUM ('internal')")
    # Drop the server default (it references the old type), swap, restore default.
    op.execute("ALTER TABLE groups ALTER COLUMN group_type DROP DEFAULT")
    op.execute(
        "ALTER TABLE groups ALTER COLUMN group_type TYPE group_type "
        "USING group_type::text::group_type"
    )
    op.execute("ALTER TABLE groups ALTER COLUMN group_type SET DEFAULT 'internal'")
    op.execute("DROP TYPE group_type_old")


def downgrade() -> None:
    # Re-add the 'contact' value (additive; safe).
    op.execute("ALTER TYPE group_type RENAME TO group_type_old")
    op.execute("CREATE TYPE group_type AS ENUM ('internal', 'contact')")
    op.execute("ALTER TABLE groups ALTER COLUMN group_type DROP DEFAULT")
    op.execute(
        "ALTER TABLE groups ALTER COLUMN group_type TYPE group_type "
        "USING group_type::text::group_type"
    )
    op.execute("ALTER TABLE groups ALTER COLUMN group_type SET DEFAULT 'internal'")
    op.execute("DROP TYPE group_type_old")
