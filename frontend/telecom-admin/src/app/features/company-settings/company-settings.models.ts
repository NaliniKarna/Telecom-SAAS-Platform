export interface PlanRef {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
}

export interface CompanySettings {
  // editable
  id: string;
  name: string;
  contact_email: string | null;
  contact_phone: string | null;
  address: string | null;
  timezone: string | null;
  logo_url: string | null;
  // read-only (platform-controlled)
  slug: string;
  status: string;
  plan: PlanRef | null;
  max_users: number | null;
  api_rate_limit: number | null;
  sms_enabled: boolean;
  voice_enabled: boolean;
  missed_call_enabled: boolean;
  freepbx_enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface CompanySettingsUpdate {
  name?: string;
  contact_email?: string | null;
  contact_phone?: string | null;
  address?: string | null;
  timezone?: string | null;
  logo_url?: string | null;
}

export interface FieldDiff {
  old: string | null;
  new: string | null;
}

export interface PendingChangeRequest {
  id: string;
  company_id: string;
  status: string;
  changes: Record<string, FieldDiff>;
  created_at: string;
}

export interface SettingsUpdateResult {
  immediate_applied: string[];
  pending_request: PendingChangeRequest | null;
}
