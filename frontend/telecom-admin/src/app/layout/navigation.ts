import { Permission } from '../core/constants/rbac.constants';

export interface NavItem {
  label: string;
  icon: string;
  route?: string;
  permissions?: Permission[];
  superAdminOnly?: boolean;
  hideForSuperAdmin?: boolean;
  placeholder?: boolean;
  children?: NavItem[];
}

export const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },

  // ---- Super Admin (platform) workspace ----
  { label: 'Companies', icon: 'apartment', route: '/companies', superAdminOnly: true },
  { label: 'Subscription Plans', icon: 'workspace_premium', route: '/subscription-plans', superAdminOnly: true },
  { label: 'Audit Logs', icon: 'receipt_long', route: '/audit-logs', superAdminOnly: true },
  { label: 'Change Requests', icon: 'rule', route: '/change-requests', superAdminOnly: true },
  { label: 'Sender ID Approvals', icon: 'verified', route: '/sms-approvals', superAdminOnly: true },
  { label: 'Telephony', icon: 'settings_phone', route: '/telephony', superAdminOnly: true },
  { label: 'Platform Settings', icon: 'settings', route: '/settings', superAdminOnly: true },

  // ---- Company Admin (tenant) workspace ----
  { label: 'Users', icon: 'group', route: '/users', permissions: [Permission.UserRead], hideForSuperAdmin: true },
  { label: 'Groups', icon: 'groups', route: '/groups', permissions: [Permission.GroupManage], hideForSuperAdmin: true },
  { label: 'API Keys', icon: 'vpn_key', route: '/api-keys', permissions: [Permission.ApiKeyRead], hideForSuperAdmin: true },
  {
    label: 'Contacts', icon: 'contacts',
    permissions: [Permission.ContactRead], hideForSuperAdmin: true,
    children: [
      { label: 'Contacts', icon: 'person', route: '/contacts', permissions: [Permission.ContactRead], hideForSuperAdmin: true },
      { label: 'Contact Groups', icon: 'format_list_bulleted', route: '/contact-lists', permissions: [Permission.ContactRead], hideForSuperAdmin: true },
    ],
  },
  { label: 'Company Settings', icon: 'business', route: '/company-settings', permissions: [Permission.CompanyRead], hideForSuperAdmin: true },

  // ---- SMS (collapsible) ----
  {
    label: 'SMS', icon: 'sms',
    permissions: [Permission.SmsRead], hideForSuperAdmin: true,
    children: [
      { label: 'Sender IDs', icon: 'badge', route: '/sms/sender-ids', permissions: [Permission.SmsRead], hideForSuperAdmin: true },
      { label: 'Templates', icon: 'description', route: '/sms/templates', permissions: [Permission.SmsRead], hideForSuperAdmin: true },
      { label: 'Campaigns', icon: 'campaign', route: '/sms/campaigns', permissions: [Permission.SmsRead], hideForSuperAdmin: true },
      { label: 'Messages', icon: 'inbox', route: '/sms/messages', permissions: [Permission.SmsRead], hideForSuperAdmin: true },
      { label: 'Analytics', icon: 'insights', route: '/sms/analytics', permissions: [Permission.SmsAnalytics], hideForSuperAdmin: true },
    ],
  },

  // ---- Voice (collapsible) ----
  {
    label: 'Voice', icon: 'call',
    permissions: [Permission.VoiceRead], hideForSuperAdmin: true,
    children: [
      { label: 'Dashboard', icon: 'dashboard', route: '/voice/dashboard', permissions: [Permission.VoiceRead], hideForSuperAdmin: true },
      { label: 'Extensions', icon: 'phone', route: '/voice/extensions', permissions: [Permission.VoiceRead], hideForSuperAdmin: true },
      { label: 'Dialer', icon: 'dialpad', route: '/voice/dialer', permissions: [Permission.VoiceDial], hideForSuperAdmin: true },
      { label: 'Active Calls', icon: 'phone_in_talk', route: '/voice/active', permissions: [Permission.VoiceRead], hideForSuperAdmin: true },
      { label: 'Call History', icon: 'history', route: '/voice/calls', permissions: [Permission.VoiceRead], hideForSuperAdmin: true },
      { label: 'Analytics', icon: 'insights', route: '/voice/analytics', permissions: [Permission.VoiceRead], hideForSuperAdmin: true },
    ],
  },

  // ---- Missed Calls (collapsible) ----
  {
    label: 'Missed Calls', icon: 'phone_missed',
    permissions: [Permission.MissedCallRead], hideForSuperAdmin: true,
    children: [
      { label: 'Dashboard', icon: 'dashboard', route: '/missed-calls/dashboard', permissions: [Permission.MissedCallRead], hideForSuperAdmin: true },
      { label: 'All Missed Calls', icon: 'list', route: '/missed-calls/list', permissions: [Permission.MissedCallRead], hideForSuperAdmin: true },
    ],
  },
];
