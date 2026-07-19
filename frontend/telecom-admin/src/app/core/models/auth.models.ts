import { Permission, RoleName } from '../constants/rbac.constants';

/** Response from POST /auth/login and /auth/refresh. */
export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

/** Response from GET /auth/me. */
export interface CurrentUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  company_id: string | null;
  roles: RoleName[];
  permissions: Permission[];
  is_email_verified: boolean;
  last_login_at: string | null;
  avatar_url: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

/** Payload for public company self-registration (POST /registration). */
export interface CompanyRegistrationRequest {
  company_name: string;
  admin_first_name: string;
  admin_last_name?: string | null;
  admin_email: string;
  password: string;
  contact_phone?: string | null;
}

/** Response from POST /registration. */
export interface RegistrationResult {
  status: string;
  message: string;
}

/** Standard error envelope returned by the API. */
export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: unknown;
}

export interface ApiErrorResponse {
  data: null;
  meta?: { request_id?: string };
  errors: ApiErrorDetail[];
}
