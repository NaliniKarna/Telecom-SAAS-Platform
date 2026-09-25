export type VoiceCampaignStatus =
  | 'draft' | 'scheduled' | 'processing' | 'partially_completed'
  | 'completed' | 'failed' | 'cancelled';

export type VoiceCampaignRecipientStatus =
  | 'queued' | 'processing' | 'ready' | 'calling' | 'answered'
  | 'no_answer' | 'busy' | 'completed' | 'failed';

export interface TtsUsageSummary {
  usage_month: string;
  monthly_limit: number | null; // null = unlimited
  consumed_characters: number;
  reserved_characters: number;
  available_characters: number | null; // null = unlimited
}

export interface VoiceCampaign {
  id: string;
  name: string;
  contact_list_id: string | null;
  voice_template_id: string | null;
  voice_id: string | null;
  resolved_voice_id: string | null;
  status: VoiceCampaignStatus;
  total_recipients: number;
  estimated_tts_characters: number;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface VoiceCampaignListItem {
  id: string;
  name: string;
  status: VoiceCampaignStatus;
  total_recipients: number;
  estimated_tts_characters: number;
  scheduled_at: string | null;
  created_at: string;
}

export interface VoiceCampaignRecipient {
  id: string;
  contact_id: string | null;
  phone_e164: string;
  resolved_name: string | null;
  rendered_text: string;
  tts_char_count: number;
  audio_id: string | null;
  status: VoiceCampaignRecipientStatus;
  error_message: string | null;
  correlation_id: string;
  created_at: string;
}

export interface VoiceCampaignCreate {
  name: string;
  contact_list_id: string;
  voice_template_id: string;
  voice_id?: string | null;
  scheduled_at?: string | null;
}

export interface VoiceCampaignUpdate {
  name?: string;
  contact_list_id?: string;
  voice_template_id?: string;
  voice_id?: string | null;
  scheduled_at?: string | null;
}

export interface VoiceCampaignEstimate {
  recipient_count: number;
  estimated_characters: number;
  usage: TtsUsageSummary;
  can_start: boolean;
  errors: string[];
}

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
