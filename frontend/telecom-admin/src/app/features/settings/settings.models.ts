export interface PlatformSettings {
  id: string;
  platform_name: string;
  platform_logo_url: string | null;
  support_email: string | null;
  support_phone: string | null;
  default_plan_id: string | null;
  default_user_limit: number | null;
  default_api_key_limit: number | null;
  default_api_rate_limit: number | null;
  sms_module_enabled: boolean;
  voice_module_enabled: boolean;
  missed_call_module_enabled: boolean;
  api_access_module_enabled: boolean;
  jwt_expiry_minutes: number;
  password_min_length: number;
  password_require_uppercase: boolean;
  password_require_number: boolean;
  password_require_symbol: boolean;
  created_at: string;
  updated_at: string;
}

export type PlatformSettingsUpdate = Partial<
  Omit<PlatformSettings, 'id' | 'created_at' | 'updated_at'>
>;
