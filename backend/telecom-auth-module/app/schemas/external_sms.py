"""Schemas for the external, API-key-authenticated SMS send endpoint.

Deliberately narrow: `sender_id` and `template_id` reference objects created
through the existing Company Admin console (sender-ID approval, template
authoring) — this endpoint does not let a programmatic caller invent a
sender or free-form message body, it only lets them trigger a send using
assets the company already set up and had approved.
"""
import uuid

from pydantic import BaseModel, ConfigDict, Field


class ExternalSmsSendRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to: str = Field(
        min_length=5, max_length=40,
        description="Destination phone number (Nepal number; any common "
                     "format is accepted and normalized to E.164).",
    )
    sender_id: uuid.UUID = Field(
        description="An existing, approved SMS Sender ID belonging to your company."
    )
    template_id: uuid.UUID = Field(
        description="An existing SMS Template belonging to your company."
    )
    recipient_name: str | None = Field(
        default=None, max_length=100,
        description="Optional — used to fill the template's {{name}} placeholder "
                     "and to label the contact record if one has to be created.",
    )


class ExternalSmsSendResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool = True
    campaign_id: uuid.UUID
    contact_id: uuid.UUID
    status: str
    message: str = "Queued for delivery."