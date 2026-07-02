export interface FieldDiff {
  old: string | null;
  new: string | null;
}

export interface ChangeRequest {
  id: string;
  company_id: string;
  company_name: string | null;
  requested_by: string | null;
  requester_name: string | null;
  status: string;
  changes: Record<string, FieldDiff>;
  decision_reason: string | null;
  reviewed_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface RecentActivity {
  id: string;
  company_id: string | null;
  company_name: string | null;
  action: string;
  changed_fields: string[];
  new_values: Record<string, unknown> | null;
  created_at: string | null;
}

export interface SettingsUpdateResult {
  immediate_applied: string[];
  pending_request: ChangeRequest | null;
}
