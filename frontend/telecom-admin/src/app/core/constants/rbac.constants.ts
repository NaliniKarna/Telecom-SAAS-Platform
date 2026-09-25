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
  // Voice
  VoiceRead = 'voice.read',
  VoiceManage = 'voice.manage',
  VoiceDial = 'voice.dial',
  // Missed Calls
  MissedCallRead = 'missed_call.read',
  MissedCallManage = 'missed_call.manage',
  // AI Voice / TTS foundation
  AiVoiceRead = 'ai_voice.read',
  AiVoiceManage = 'ai_voice.manage',
  AiVoicePreview = 'ai_voice.preview',
  // Voice Campaigns (Phase 4A)
  AiVoiceCampaignRead = 'ai_voice.campaign.read',
  AiVoiceCampaignManage = 'ai_voice.campaign.manage',
  // Audit & stats
  AuditRead = 'audit.read',
  StatsRead = 'stats.read',
}
