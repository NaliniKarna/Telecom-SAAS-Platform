export type VoiceStatus = 'active' | 'inactive';
export type VoiceTemplateStatus = 'active' | 'inactive';

export interface Voice {
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

export interface VoiceTemplate {
  id: string;
  name: string;
  description: string | null;
  text: string;
  language: string;
  voice_id: string;
  variables: string[];
  status: VoiceTemplateStatus;
  created_at: string;
  updated_at: string;
}

export interface VoiceTemplateCreate {
  name: string;
  description?: string | null;
  text: string;
  language: string;
  voice_id: string;
  status?: VoiceTemplateStatus | null;
}

export interface VoiceTemplateUpdate {
  name?: string;
  description?: string | null;
  text?: string;
  language?: string;
  voice_id?: string;
  status?: VoiceTemplateStatus | null;
}

export interface RenderResult {
  rendered_text: string;
  missing_variables: string[];
}

export interface TtsPreview {
  id: string;
  voice_template_id: string;
  voice_id: string;
  rendered_text: string;
  audio_url: string;
  duration_seconds: number | null;
  char_count: number;
  created_at: string;
}

export interface Paginated<T> {
  data: T[];
  meta: { page: number; size: number; total: number; pages: number };
}
