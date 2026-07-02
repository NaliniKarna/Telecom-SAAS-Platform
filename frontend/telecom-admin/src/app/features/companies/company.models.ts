export type CompanyStatus = 'active' | 'suspended' | 'deactivated';

export interface SubscriptionPlan {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  default_max_users: number | null;
  default_api_rate_limit: number | null;
  default_sms_enabled: boolean;
  default_voice_enabled: boolean;
  default_missed_call_enabled: boolean;
  default_freepbx_enabled: boolean;
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  status: CompanyStatus;
  plan_id: string | null;
  plan: SubscriptionPlan | null;
  contact_email: string | null;
  contact_phone: string | null;
  sms_enabled: boolean;
  voice_enabled: boolean;
  missed_call_enabled: boolean;
  freepbx_enabled: boolean;
  max_users: number | null;
  api_rate_limit: number | null;
  created_at: string;
  updated_at: string;
}

export interface CompanyListPlanRef {
  id: string;
  name: string;
}

export interface CompanyListItem {
  id: string;
  name: string;
  slug: string;
  status: CompanyStatus;
  plan_id: string | null;
  plan: CompanyListPlanRef | null;
  contact_email: string | null;
  contact_phone: string | null;
  created_at: string;
}

export interface CompanyCreate {
  name: string;
  slug: string;
  plan_id?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  sms_enabled?: boolean;
  voice_enabled?: boolean;
  missed_call_enabled?: boolean;
  freepbx_enabled?: boolean;
  max_users?: number | null;
  api_rate_limit?: number | null;
}

export interface CompanyUpdate {
  name?: string;
  plan_id?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  sms_enabled?: boolean;
  voice_enabled?: boolean;
  missed_call_enabled?: boolean;
  freepbx_enabled?: boolean;
  max_users?: number | null;
  api_rate_limit?: number | null;
}

export interface PageMeta {
  page: number;
  size: number;
  total: number;
  pages: number;
}

export interface PagedResponse<T> {
  data: T[];
  meta: PageMeta;
  errors: unknown[];
}