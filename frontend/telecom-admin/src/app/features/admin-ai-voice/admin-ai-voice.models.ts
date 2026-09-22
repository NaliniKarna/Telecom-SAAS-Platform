export type VoiceStatus = 'active' | 'inactive';

export interface AdminVoice {
  id: string;
  name: string;
  language: string;
  gender: string | null;
  description: string | null;
  provider: string;
  provider_voice_id: string;
  status: VoiceStatus;
  created_at: string;
  updated_at: string;
}

export interface VoiceCreate {
  name: string;
  language: string;
  gender?: string | null;
  description?: string | null;
  provider: string;
  provider_voice_id: string;
  status?: VoiceStatus | null;
}

export type VoiceUpdate = Partial<VoiceCreate>;

export interface PlanVoices {
  voice_ids: string[];
}

export interface AdminTtsPreviewRequest {
  text: string;
  voice_id: string;
}

export interface AdminTtsPreviewResponse {
  voice_id: string;
  text: string;
  audio_url: string;
  duration_seconds: number | null;
  char_count: number;
}

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
