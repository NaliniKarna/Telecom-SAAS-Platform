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


class ChangeRequestStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class GroupStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


class GroupType(str, enum.Enum):
    # Groups are organizational user groups only. Contacts use their own
    # dedicated contact_lists tables, so there is no CONTACT group type.
    INTERNAL = "internal"


class ApiKeyStatus(str, enum.Enum):
    # Derived at read time from revoked_at / expires_at, not stored.
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


class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"
    PASSWORD_RESET = "password_reset"


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

    # SMS. Foundation (sender IDs + templates) uses sms.read / sms.manage;
    # the Campaign Engine adds sms.send (schedule / send / cancel) and Tracking
    # & Analytics adds sms.analytics. All four are implemented and enforced.
    SMS_READ = "sms.read"
    SMS_MANAGE = "sms.manage"
    SMS_SEND = "sms.send"
    SMS_ANALYTICS = "sms.analytics"

    # Audit & stats
    AUDIT_READ = "audit.read"
    STATS_READ = "stats.read"


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
    },
    RoleName.COMPANY_USER: {
        Permission.USER_READ,
    },
}