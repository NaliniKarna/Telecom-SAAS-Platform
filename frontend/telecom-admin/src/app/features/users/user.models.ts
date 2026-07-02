export type UserStatus = 'active' | 'inactive' | 'pending' | 'locked';
export type AssignableRole = 'company_admin' | 'company_user';

export interface CompanyUser {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  status: UserStatus;
  is_email_verified: boolean;
  roles: string[];
  last_login_at: string | null;
  created_at: string;
}

export interface UserListItem {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  status: UserStatus;
  roles: string[];
  created_at: string;
}

export interface UserInvite {
  email: string;
  first_name?: string | null;
  last_name?: string | null;
  role: AssignableRole;
}

export interface UserUpdate {
  first_name?: string | null;
  last_name?: string | null;
  role?: AssignableRole;
}

export interface PageMeta { page: number; size: number; total: number; pages: number; }
export interface PagedResponse<T> { data: T[]; meta: PageMeta; errors: unknown[]; }
