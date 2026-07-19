// ── Voice Platform TypeScript interfaces ──
// Mirrors backend app/schemas/voice.py — keep in sync.

export type AgentStatus = 'available' | 'busy' | 'away' | 'offline';
export type CallDirection = 'inbound' | 'outbound';
export type CallStatus =
  | 'initiated'
  | 'ringing'
  | 'answered'
  | 'busy'
  | 'no_answer'
  | 'failed'
  | 'cancelled'
  | 'completed';

// ── Extensions ──

export interface VoiceExtension {
  id: string;
  company_id: string;
  extension_number: string;
  display_name: string;
  description: string | null;
  context: string;
  technology: string;
  enabled: boolean;
  user_id: string | null;
  agent_status: AgentStatus;
  last_seen_at: string | null;
  created_at: string;
  updated_at: string;
  assigned_user_name: string | null;
  assigned_user_email: string | null;
}

export interface VoiceExtensionCreate {
  extension_number: string;
  display_name: string;
  description?: string | null;
  context?: string;
  technology?: string;
  enabled?: boolean;
  user_id?: string | null;
}

export interface VoiceExtensionUpdate {
  display_name?: string;
  description?: string | null;
  context?: string;
  technology?: string;
  enabled?: boolean;
  user_id?: string | null;
}

// ── Calls ──

export interface OriginateRequest {
  caller_extension_id?: string | null;
  caller_number?: string | null;
  destination_number: string;
  caller_id_override?: string | null;
}

export interface VoiceCallLog {
  id: string;
  company_id: string;
  connection_id: string | null;
  direction: CallDirection;
  status: CallStatus;
  caller_number: string;
  callee_number: string;
  caller_extension_id: string | null;
  callee_extension_id: string | null;
  started_at: string;
  answered_at: string | null;
  ended_at: string | null;
  duration_seconds: number | null;
  ring_duration_seconds: number | null;
  action_id: string | null;
  hangup_cause: string | null;
  recording_url: string | null;
  initiated_by: string | null;
  created_at: string;
  caller_extension_number: string | null;
  callee_extension_number: string | null;
  initiator_name: string | null;
}

export interface PaginatedCallLogs {
  items: VoiceCallLog[];
  total: number;
  offset: number;
  limit: number;
}

// ── Analytics ──

export interface VoiceOverviewStats {
  total_calls: number;
  answered_calls: number;
  answer_rate_pct: number;
  avg_duration_seconds: number;
  total_duration_seconds: number;
  active_calls: number;
  outbound_calls: number;
  inbound_calls: number;
  failed_calls: number;
}

export interface TimeseriesPoint {
  date: string;
  total: number;
  answered: number;
  failed: number;
}

export interface VoiceTimeseriesStats {
  points: TimeseriesPoint[];
  period_days: number;
}

export interface ExtensionStatusSummary {
  available: number;
  busy: number;
  away: number;
  offline: number;
  total: number;
}
