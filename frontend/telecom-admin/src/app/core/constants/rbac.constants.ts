/**
 * RBAC catalog — mirrors the backend `core/constants.py`.
 * Keep these in sync with the API; permission codes are the contract.
 */
export enum RoleName {
  SuperAdmin = 'super_admin',
  CompanyAdmin = 'company_admin',
  CompanyUser = 'company_user',
}

export enum Permission {
  // Company
  CompanyCreate = 'company.create',
  CompanyRead = 'company.read',
  CompanyUpdate = 'company.update',
  CompanyDelete = 'company.delete',
  CompanyActivate = 'company.activate',
  CompanyDeactivate = 'company.deactivate',
  // User
  UserCreate = 'user.create',
  UserRead = 'user.read',
  UserUpdate = 'user.update',
  UserDelete = 'user.delete',
  UserActivate = 'user.activate',
  UserDeactivate = 'user.deactivate',
  // Group
  GroupManage = 'group.manage',
  // API keys
  ApiKeyGenerate = 'apikey.generate',
  ApiKeyRevoke = 'apikey.revoke',
  ApiKeyRead = 'apikey.read',
  // Contacts
  ContactRead = 'contact.read',
  ContactManage = 'contact.manage',
  // SMS
  SmsRead = 'sms.read',
  SmsManage = 'sms.manage',
  SmsSend = 'sms.send',
  SmsAnalytics = 'sms.analytics',
  // Audit & stats
  AuditRead = 'audit.read',
  StatsRead = 'stats.read',
}
