export interface SubscriptionPlan {
  id: string;
  code: string;
  name: string;
  description: string | null;
  is_active: boolean;
  default_max_users: number | null;
  default_api_rate_limit: number | null;
  default_max_api_keys: number | null;
  default_monthly_sms_limit: number | null;
  default_monthly_voice_minutes: number | null;
  default_sms_enabled: boolean;
  default_voice_enabled: boolean;
  default_missed_call_enabled: boolean;
  default_freepbx_enabled: boolean;
  default_api_access_enabled: boolean;
  default_ai_voice_enabled: boolean;
  default_monthly_tts_characters: number | null;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface PlanListItem {
  id: string;
  code: string;
  name: string;
  is_active: boolean;
  usage_count: number;
}

export interface PlanCreate {
  code: string;
  name: string;
  description?: string | null;
  is_active?: boolean;
  default_max_users?: number | null;
  default_api_rate_limit?: number | null;
  default_max_api_keys?: number | null;
  default_monthly_sms_limit?: number | null;
  default_monthly_voice_minutes?: number | null;
  default_sms_enabled?: boolean;
  default_voice_enabled?: boolean;
  default_missed_call_enabled?: boolean;
  default_freepbx_enabled?: boolean;
  default_api_access_enabled?: boolean;
  default_ai_voice_enabled?: boolean;
  default_monthly_tts_characters?: number | null;
}

export type PlanUpdate = Partial<Omit<PlanCreate, 'code'>>;

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

export interface PlanDetailResponse {
  data: SubscriptionPlan;
  usage_count: number;
  errors: unknown[];
}