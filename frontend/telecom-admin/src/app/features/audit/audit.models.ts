export interface AuditLog {
  id: number;
  action: string;
  entity_type: string;
  entity_id: string | null;
  description: string | null;
  company_id: string | null;
  company_name: string | null;
  actor_id: string | null;
  actor_email: string | null;
  actor_name: string | null;
  ip_address: string | null;
  old_values: Record<string, unknown> | null;
  new_values: Record<string, unknown> | null;
  created_at: string;
}

export interface AuditFacets {
  actions: string[];
  modules: string[];
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

export interface AuditQuery {
  page?: number;
  size?: number;
  search?: string;
  company_id?: string;
  actor_id?: string;
  action?: string;
  entity_type?: string;
  date_from?: string;
  date_to?: string;
  sort_dir?: 'asc' | 'desc';
}
