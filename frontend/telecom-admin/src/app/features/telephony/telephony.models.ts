/**
 * Telephony (FreePBX / Asterisk) types — platform PBX infrastructure.
 *
 * Provider-managed model: these connections are managed by super admins only.
 * The AMI secret is write-only — sent on create/update, never returned; reads
 * expose `secret_set` instead.
 */

export type TelephonyStatus =
  | 'unknown'
  | 'connected'
  | 'error'
  | 'disconnected';

export interface TelephonyConnection {
  id: string;
  company_id: string | null;
  name: string;
  description: string | null;
  host: string;
  port: number;
  ami_username: string;
  use_tls: boolean;
  enabled: boolean;
  last_status: TelephonyStatus;
  last_checked_at: string | null;
  last_error: string | null;
  created_at: string;
  updated_at: string;
  is_platform_default: boolean;
  secret_set: boolean;
}

export interface TelephonyConnectionCreate {
  name: string;
  description?: string | null;
  host: string;
  port: number;
  ami_username: string;
  ami_secret: string;
  use_tls: boolean;
  enabled: boolean;
}

/** Partial update. Omit `ami_secret` to keep the stored secret. */
export interface TelephonyConnectionUpdate {
  name?: string;
  description?: string | null;
  host?: string;
  port?: number;
  ami_username?: string;
  ami_secret?: string;
  use_tls?: boolean;
  enabled?: boolean;
}

export interface ConnectionTestResult {
  connected: boolean;
  detail: string;
  latency_ms: number | null;
  provider: string;
  checked_at: string;
}
