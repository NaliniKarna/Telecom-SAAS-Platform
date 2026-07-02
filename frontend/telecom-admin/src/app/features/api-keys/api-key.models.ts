export type ApiKeyStatus = 'active' | 'revoked' | 'expired';

export interface ApiKey {
  id: string;
  name: string;
  description: string | null;
  key_prefix: string;
  status: ApiKeyStatus;
  expires_at: string | null;
  last_used_at: string | null;
  usage_count: number;
  revoked_at: string | null;
  created_at: string;
}

export interface ApiKeyCreated extends ApiKey {
  api_key: string; // plaintext — shown ONCE
}

export interface ApiKeyCreate {
  name: string;
  description?: string | null;
  expires_at?: string | null;
}

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
