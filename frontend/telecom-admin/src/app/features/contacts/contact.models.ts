export type ContactStatus = 'active' | 'inactive' | 'unsubscribed';
export type ContactNumberType = 'mobile' | 'landline' | 'unknown';

export interface Contact {
  id: string;
  first_name: string | null;
  last_name: string | null;
  mobile_raw: string | null;
  mobile_e164: string | null;
  landline_raw: string | null;
  landline_e164: string | null;
  number_type: ContactNumberType;
  email: string | null;
  tags: string[];
  notes: string | null;
  status: ContactStatus;
  created_at: string;
  updated_at: string;
}

export interface ContactListItem {
  id: string;
  first_name: string | null;
  last_name: string | null;
  mobile_e164: string | null;
  email: string | null;
  tags: string[];
  status: ContactStatus;
  created_at: string;
}

export interface ContactCreate {
  first_name?: string | null;
  last_name?: string | null;
  mobile?: string | null;
  landline?: string | null;
  email?: string | null;
  tags?: string[];
  notes?: string | null;
  status?: ContactStatus;
}

export type ContactUpdate = ContactCreate;

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}

// ---- Contact lists ----
export interface ContactGroup {
  id: string;
  name: string;
  description: string | null;
  member_count: number;
  created_at: string;
  updated_at: string;
}

export interface ContactGroupMember {
  id: string;
  contact_id: string;
  first_name: string | null;
  last_name: string | null;
  mobile_e164: string | null;
  email: string | null;
  added_at: string;
}

// ---- CSV import (C3) ----
export interface ImportRowResult {
  row_number: number;
  first_name: string | null;
  last_name: string | null;
  mobile: string | null;
  mobile_e164: string | null;
  landline: string | null;
  landline_e164: string | null;
  email: string | null;
  tags: string[];
  notes: string | null;
  status: string;
  row_status: 'valid' | 'invalid' | 'duplicate';
  errors: string[];
}

export interface ImportPreview {
  total: number;
  valid: number;
  invalid: number;
  duplicate: number;
  rows: ImportRowResult[];
}

export interface ImportCommitRow {
  first_name?: string | null;
  last_name?: string | null;
  mobile?: string | null;
  landline?: string | null;
  email?: string | null;
  tags?: string[];
  notes?: string | null;
  status?: string;
}

export interface ImportResult {
  imported: number;
  skipped_duplicates: number;
  failed: number;
  errors: string[];
}
