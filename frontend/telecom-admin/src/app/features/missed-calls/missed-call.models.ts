// ── Missed Call Platform TypeScript interfaces ──
// Mirrors backend app/schemas/missed_call.py

export type MissedCallStatus = 'new' | 'acknowledged' | 'returned' | 'closed';
export type CallbackOutcome = 'answered' | 'no_answer' | 'busy' | 'voicemail' | 'failed';

export interface MissedCallRead {
  id: string;
  company_id: string;
  caller_number: string;
  called_number: string;
  called_extension_id: string | null;
  called_extension_number: string | null;
  status: MissedCallStatus;
  received_at: string;
  ring_duration_seconds: number | null;
  source_call_id: string | null;
  assigned_to: string | null;
  assignee_name: string | null;
  callback_count: number;
  caller_name: string | null;
  created_at: string;
  updated_at: string;
}

export interface MissedCallNote {
  id: string;
  missed_call_id: string;
  author_id: string;
  author_name: string | null;
  body: string;
  created_at: string;
}

export interface MissedCallCallback {
  id: string;
  missed_call_id: string;
  performed_by: string;
  performer_name: string | null;
  extension_id: string | null;
  extension_number: string | null;
  voice_call_id: string | null;
  outcome: CallbackOutcome | null;
  duration_seconds: number | null;
  notes: string | null;
  attempted_at: string;
  created_at: string;
}

export interface MissedCallDetail extends MissedCallRead {
  notes: MissedCallNote[];
  callbacks: MissedCallCallback[];
}

export interface PaginatedMissedCalls {
  items: MissedCallRead[];
  total: number;
  offset: number;
  limit: number;
}

export interface MissedCallCreate {
  caller_number: string;
  called_number: string;
  called_extension_id?: string | null;
  received_at: string;
  ring_duration_seconds?: number | null;
  source_call_id?: string | null;
  caller_name?: string | null;
}

export interface CallbackRequest {
  extension_id?: string | null;
  caller_number?: string | null;
  notes?: string | null;
}

export interface MissedCallDashboardStats {
  missed_today: number;
  pending_callbacks: number;
  total_callbacks: number;
  callbacks_answered: number;
  callback_success_rate_pct: number;
  avg_callback_time_seconds: number;
  total_missed: number;
  by_status: Record<string, number>;
}
