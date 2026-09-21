import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Paginated, RenderResult, TtsPreview, Voice, VoiceStatus,
  VoiceTemplate, VoiceTemplateCreate, VoiceTemplateStatus, VoiceTemplateUpdate,
} from './ai-voice.models';

@Injectable({ providedIn: 'root' })
export class AiVoiceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/ai-voice`;

  // ---- Voice library ----
  listVoices(opts: { status?: VoiceStatus | null; page?: number; size?: number } = {}): Observable<Paginated<Voice>> {
    let params = new HttpParams();
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<Voice>>(`${this.base}/voices`, { params });
  }
  getVoice(id: string): Observable<Voice> {
    return this.http.get<Voice>(`${this.base}/voices/${id}`);
  }
  activateVoice(id: string): Observable<Voice> {
    return this.http.post<Voice>(`${this.base}/voices/${id}/activate`, {});
  }
  deactivateVoice(id: string): Observable<Voice> {
    return this.http.post<Voice>(`${this.base}/voices/${id}/deactivate`, {});
  }

  // ---- Voice Templates ----
  listTemplates(opts: {
    search?: string; status?: VoiceTemplateStatus | null; page?: number; size?: number;
  } = {}): Observable<Paginated<VoiceTemplate>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<VoiceTemplate>>(`${this.base}/templates`, { params });
  }
  getTemplate(id: string): Observable<VoiceTemplate> {
    return this.http.get<VoiceTemplate>(`${this.base}/templates/${id}`);
  }
  createTemplate(payload: VoiceTemplateCreate): Observable<VoiceTemplate> {
    return this.http.post<VoiceTemplate>(`${this.base}/templates`, payload);
  }
  updateTemplate(id: string, payload: VoiceTemplateUpdate): Observable<VoiceTemplate> {
    return this.http.patch<VoiceTemplate>(`${this.base}/templates/${id}`, payload);
  }
  deleteTemplate(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/templates/${id}`);
  }

  // ---- Rendering + TTS preview ----
  renderTemplate(id: string, values: Record<string, string>): Observable<RenderResult> {
    return this.http.post<RenderResult>(`${this.base}/templates/${id}/render`, { values });
  }
  generatePreview(id: string, values: Record<string, string>, voiceId?: string | null): Observable<TtsPreview> {
    return this.http.post<TtsPreview>(`${this.base}/templates/${id}/tts-preview`, {
      values, voice_id: voiceId ?? null,
    });
  }
}
