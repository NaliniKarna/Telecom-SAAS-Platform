"""Group and GroupMember models.

Groups are ORGANIZATIONAL ONLY — they do not grant permissions. Authorization
stays entirely with RBAC. A group is a tenant-scoped collection of users
(many-to-many). group_type distinguishes INTERNAL (platform users) from CONTACT
(forward-looking, for SMS/Voice/Missed-Call/Campaign modules) so we don't need
separate group models later.

Membership is a hard association row: removing a member (or soft-deleting the
group) deletes the membership row(s); the underlying users are never affected.
"""
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import GroupStatus, GroupType
from app.db.base import Base, SoftDeleteMixin, TimestampMixin, UUIDPkMixin

if TYPE_CHECKING:
    from app.models.user import User


class Group(Base, UUIDPkMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "groups"

    company_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    status: Mapped[GroupStatus] = mapped_column(
        SAEnum(GroupStatus, name="group_status",
               values_callable=lambda e: [m.value for m in e]),
        default=GroupStatus.ACTIVE, nullable=False, index=True,
    )
    group_type: Mapped[GroupType] = mapped_column(
        SAEnum(GroupType, name="group_type",
               values_callable=lambda e: [m.value for m in e]),
        default=GroupType.INTERNAL, nullable=False, index=True,
    )

    members: Mapped[list["GroupMember"]] = relationship(
        back_populates="group",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class GroupMember(Base, UUIDPkMixin):
    __tablename__ = "group_members"
    __table_args__ = (
        UniqueConstraint("group_id", "user_id", name="uq_group_member"),
    )

    group_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PGUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    group: Mapped["Group"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(lazy="selectin")  # noqa: F821
