"""Application-level constants mirroring DB enums and the permission catalog."""
import enum


class RoleName(str, enum.Enum):
    SUPER_ADMIN = "super_admin"
    COMPANY_ADMIN = "company_admin"
    COMPANY_USER = "company_user"


class UserStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    LOCKED = "locked"


class CompanyStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    DEACTIVATED = "deactivated"
    PENDING_APPROVAL = "pending_approval"
    REJECTED = "rejected"


class ChangeRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GroupStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class GroupType(str, enum.Enum):
    INTERNAL = "internal"


class ApiKeyStatus(str, enum.Enum):
    ACTIVE = "active"
    REVOKED = "revoked"
    EXPIRED = "expired"


class ContactStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    UNSUBSCRIBED = "unsubscribed"


class ContactNumberType(str, enum.Enum):
    MOBILE = "mobile"
    LANDLINE = "landline"
    UNKNOWN = "unknown"


class SenderStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SenderApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class SmsTemplateStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class SmsCampaignStatus(str, enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    PROCESSING = "processing"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    FAILED = "failed"


class SmsCampaignSource(str, enum.Enum):
    CONTACT_LIST = "contact_list"
    CONTACTS = "contacts"


class SmsMessageStatus(str, enum.Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"


class TelephonyProvider(str, enum.Enum):
    NULL = "null"
    AMI = "ami"


class TelephonyConnectionStatus(str, enum.Enum):
    UNKNOWN = "unknown"
    CONNECTED = "connected"
    ERROR = "error"
    DISABLED = "disabled"


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"


# ── Voice Platform (Phase 5) ──────────────────────────────────────────────────

class AgentStatus(str, enum.Enum):
    AVAILABLE = "available"
    BUSY = "busy"
    AWAY = "away"
    OFFLINE = "offline"


class CallDirection(str, enum.Enum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class CallStatus(str, enum.Enum):
    INITIATED = "initiated"
    RINGING = "ringing"
    ANSWERED = "answered"
    BUSY = "busy"
    NO_ANSWER = "no_answer"
    FAILED = "failed"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


ACTIVE_CALL_STATUSES = frozenset([
    CallStatus.INITIATED.value,
    CallStatus.RINGING.value,
    CallStatus.ANSWERED.value,
])


# ── Missed Call Platform (Phase 6) ────────────────────────────────────────────

class MissedCallStatus(str, enum.Enum):
    """Lifecycle status of a missed-call record."""
    NEW = "new"                   # just detected, nobody has acted on it
    ACKNOWLEDGED = "acknowledged" # someone has seen / claimed it
    RETURNED = "returned"         # a callback was made (regardless of outcome)
    CLOSED = "closed"             # resolved — no further action needed


class CallbackOutcome(str, enum.Enum):
    """Result of a callback attempt."""
    ANSWERED = "answered"
    NO_ANSWER = "no_answer"
    BUSY = "busy"
    VOICEMAIL = "voicemail"
    FAILED = "failed"


class Permission(str, enum.Enum):
    """Canonical permission catalog (resource.action)."""

    # Company management
    COMPANY_CREATE = "company.create"
    COMPANY_READ = "company.read"
    COMPANY_UPDATE = "company.update"
    COMPANY_DELETE = "company.delete"
    COMPANY_ACTIVATE = "company.activate"
    COMPANY_DEACTIVATE = "company.deactivate"

    # User management
    USER_CREATE = "user.create"
    USER_READ = "user.read"
    USER_UPDATE = "user.update"
    USER_DELETE = "user.delete"
    USER_ACTIVATE = "user.activate"
    USER_DEACTIVATE = "user.deactivate"

    # Group management
    GROUP_MANAGE = "group.manage"

    # API keys
    APIKEY_GENERATE = "apikey.generate"
    APIKEY_REVOKE = "apikey.revoke"
    APIKEY_READ = "apikey.read"

    # Contacts
    CONTACT_READ = "contact.read"
    CONTACT_MANAGE = "contact.manage"

    # SMS
    SMS_READ = "sms.read"
    SMS_MANAGE = "sms.manage"
    SMS_SEND = "sms.send"
    SMS_ANALYTICS = "sms.analytics"

    # Audit & stats
    AUDIT_READ = "audit.read"
    STATS_READ = "stats.read"

    # Telephony / FreePBX-Asterisk integration layer (super admin only)
    TELEPHONY_READ = "telephony.read"
    TELEPHONY_MANAGE = "telephony.manage"

    # Voice Platform (Phase 5)
    VOICE_READ = "voice.read"
    VOICE_MANAGE = "voice.manage"
    VOICE_DIAL = "voice.dial"

    # Missed Call Platform (Phase 6)
    # missed_call.read   : view missed call log, dashboard, history
    # missed_call.manage : acknowledge, assign, add notes, update status, callback
    MISSED_CALL_READ = "missed_call.read"
    MISSED_CALL_MANAGE = "missed_call.manage"


# Role -> permission mapping. Super admin is handled as a wildcard at check time.
ROLE_PERMISSIONS: dict[RoleName, set[Permission]] = {
    RoleName.SUPER_ADMIN: set(Permission),  # all
    RoleName.COMPANY_ADMIN: {
        Permission.COMPANY_READ,
        Permission.USER_CREATE,
        Permission.USER_READ,
        Permission.USER_UPDATE,
        Permission.USER_DELETE,
        Permission.USER_ACTIVATE,
        Permission.USER_DEACTIVATE,
        Permission.GROUP_MANAGE,
        Permission.APIKEY_GENERATE,
        Permission.APIKEY_REVOKE,
        Permission.APIKEY_READ,
        Permission.CONTACT_READ,
        Permission.CONTACT_MANAGE,
        Permission.SMS_READ,
        Permission.SMS_MANAGE,
        Permission.SMS_SEND,
        Permission.SMS_ANALYTICS,
        Permission.AUDIT_READ,
        Permission.STATS_READ,
        Permission.VOICE_READ,
        Permission.VOICE_MANAGE,
        Permission.VOICE_DIAL,
        Permission.MISSED_CALL_READ,
        Permission.MISSED_CALL_MANAGE,
    },
    RoleName.COMPANY_USER: {
        Permission.USER_READ,
        Permission.VOICE_READ,
        Permission.MISSED_CALL_READ,
    },
}
