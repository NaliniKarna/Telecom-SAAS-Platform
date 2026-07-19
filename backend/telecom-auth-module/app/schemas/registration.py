"""Public company self-registration DTOs.

Collects only what's needed to create a registration request: the company name,
the prospective admin's identity + credentials, and an optional contact phone.
The company is created in PENDING_APPROVAL and the admin in PENDING; neither can
access the platform until a super admin approves (see RegistrationService).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class CompanyRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    company_name: str = Field(min_length=2, max_length=255)
    admin_first_name: str = Field(min_length=1, max_length=100)
    admin_last_name: Optional[str] = Field(default=None, max_length=100)
    admin_email: EmailStr
    # The password the admin will use to sign in AFTER approval. Min length is
    # enforced here; the shared password policy still applies downstream.
    password: str = Field(min_length=10, max_length=128)
    contact_phone: Optional[str] = Field(default=None, max_length=30)


class RegistrationResult(BaseModel):
    """Deliberately minimal + non-committal: we don't leak whether the email
    already existed, and we always steer the user to verify their email."""
    status: str = "pending_verification"
    message: str = (
        "Registration received. Check your email to verify your address, then "
        "your company will be reviewed for approval."
    )


class PendingRegistration(BaseModel):
    """Super-admin review row: the pending company + its admin + whether the
    admin has verified their email (approval is blocked until they have)."""
    model_config = ConfigDict(from_attributes=True)

    company_id: uuid.UUID
    company_name: str
    slug: str
    status: str
    contact_phone: Optional[str] = None
    admin_user_id: Optional[uuid.UUID] = None
    admin_email: Optional[str] = None
    admin_name: Optional[str] = None
    admin_email_verified: bool = False
    submitted_at: datetime


class RegistrationDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Optional[str] = Field(default=None, max_length=500)
