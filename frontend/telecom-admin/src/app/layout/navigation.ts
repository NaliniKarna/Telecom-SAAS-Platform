import { Permission } from '../core/constants/rbac.constants';

export interface NavItem {
  label: string;
  icon: string;
  /**
   * Target route. Optional: a group parent (one carrying `children`) has no
   * route of its own — clicking it toggles expansion instead of navigating.
   */
  route?: string;
  /** If set, the item shows only when the user holds one of these. */
  permissions?: Permission[];
  /** If true, the item shows only for super-admin users. */
  superAdminOnly?: boolean;
  /** If true, the item is hidden from super-admins (company-scoped feature). */
  hideForSuperAdmin?: boolean;
  /** If true, the route is a not-yet-built placeholder ("coming soon"). */
  placeholder?: boolean;
  /**
   * Child items. When present this item renders as a collapsible group: its
   * children appear only while the group is expanded, and the parent is
   * highlighted whenever one of the child routes is active. Visibility of the
   * group as a whole still respects the parent's role/permission flags, and
   * each child is additionally filtered by its own flags.
   */
  children?: NavItem[];
}

/**
 * Primary navigation, filtered at render time by role + permission so the
 * sidebar always reflects what the current user can actually reach.
 *
 * Two distinct workspaces share this list:
 *
 * - Super Admin (platform owner): Dashboard, Companies, Subscription Plans,
 *   Audit Logs, Platform Settings. All marked superAdminOnly.
 *
 * - Company Admin (tenant owner): Dashboard, Users, Groups, API Keys, Company
 *   Settings, and the SMS group. All marked hideForSuperAdmin so they never
 *   appear in the platform workspace, and each gated by the relevant
 *   company-scoped permission.
 *
 * Audit Logs is intentionally superAdminOnly even though company_admin also
 * holds audit.read in RBAC: the Audit Logs screen is the PLATFORM-WIDE trail
 * and must never be exposed to a tenant. (The backend route is also locked to
 * super admin, so this is defence-in-depth, not the only guard.)
 *
 * SMS pages are grouped under a single collapsible "SMS" parent. Routes,
 * permissions, and components are unchanged — only the menu presentation is
 * grouped. The group is gated by sms.read (so it hides entirely for users
 * without any SMS access); the Analytics child additionally requires
 * sms.analytics, exactly as before.
 */
export const NAV_ITEMS: NavItem[] = [
  // Shared landing — the dashboard component renders a per-role view.
  { label: 'Dashboard', icon: 'dashboard', route: '/dashboard' },

  // ---- Super Admin (platform) workspace ----
  {
    label: 'Companies',
    icon: 'apartment',
    route: '/companies',
    superAdminOnly: true,
  },
  {
    label: 'Subscription Plans',
    icon: 'workspace_premium',
    route: '/subscription-plans',
    superAdminOnly: true,
  },
  {
    label: 'Audit Logs',
    icon: 'receipt_long',
    route: '/audit-logs',
    superAdminOnly: true,
  },
  {
    label: 'Change Requests',
    icon: 'rule',
    route: '/change-requests',
    superAdminOnly: true,
  },
  {
    label: 'Sender ID Approvals',
    icon: 'verified',
    route: '/sms-approvals',
    superAdminOnly: true,
  },
  {
    label: 'Platform Settings',
    icon: 'settings',
    route: '/settings',
    superAdminOnly: true,
  },

  // ---- Company Admin (tenant) workspace ----
  {
    label: 'Users',
    icon: 'group',
    route: '/users',
    permissions: [Permission.UserRead],
    hideForSuperAdmin: true,
  },
  {
    label: 'Groups',
    icon: 'groups',
    route: '/groups',
    permissions: [Permission.GroupManage],
    hideForSuperAdmin: true,
  },
  {
    label: 'API Keys',
    icon: 'vpn_key',
    route: '/api-keys',
    permissions: [Permission.ApiKeyRead],
    hideForSuperAdmin: true,
  },
  {
    label: 'Contacts',
    icon: 'contacts',
    route: '/contacts',
    permissions: [Permission.ContactRead],
    hideForSuperAdmin: true,
  },
  {
    label: 'Contact Lists',
    icon: 'format_list_bulleted',
    route: '/contact-lists',
    permissions: [Permission.ContactRead],
    hideForSuperAdmin: true,
  },
  
  // ---- SMS (collapsible group) ----
  {
    label: 'SMS',
    icon: 'sms',
    permissions: [Permission.SmsRead],
    hideForSuperAdmin: true,
    children: [
      {
        label: 'Sender IDs',
        icon: 'badge',
        route: '/sms/sender-ids',
        permissions: [Permission.SmsRead],
        hideForSuperAdmin: true,
      },
      {
        label: 'Templates',
        icon: 'description',
        route: '/sms/templates',
        permissions: [Permission.SmsRead],
        hideForSuperAdmin: true,
      },
      {
        label: 'Campaigns',
        icon: 'campaign',
        route: '/sms/campaigns',
        permissions: [Permission.SmsRead],
        hideForSuperAdmin: true,
      },
      {
        label: 'Messages',
        icon: 'inbox',
        route: '/sms/messages',
        permissions: [Permission.SmsRead],
        hideForSuperAdmin: true,
      },
      {
        label: 'Analytics',
        icon: 'insights',
        route: '/sms/analytics',
        permissions: [Permission.SmsAnalytics],
        hideForSuperAdmin: true,
      },
    ],
  },
  {
    label: 'Company Settings',
    icon: 'business',
    route: '/company-settings',
    permissions: [Permission.CompanyRead],
    hideForSuperAdmin: true,
  },
];