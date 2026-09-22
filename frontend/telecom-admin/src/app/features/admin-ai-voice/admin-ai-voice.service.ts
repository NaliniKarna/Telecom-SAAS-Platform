import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AdminTtsPreviewRequest, AdminTtsPreviewResponse, AdminVoice,
  Paginated, PlanVoices, VoiceCreate, VoiceStatus, VoiceUpdate,
} from './admin-ai-voice.models';

@Injectable({ providedIn: 'root' })
export class AdminAiVoiceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/admin/ai-voice`;

  listVoices(opts: {
    search?: string; status?: VoiceStatus | null; page?: number; size?: number;
  } = {}): Observable<Paginated<AdminVoice>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<AdminVoice>>(`${this.base}/voices`, { params });
  }
  getVoice(id: string): Observable<AdminVoice> {
    return this.http.get<AdminVoice>(`${this.base}/voices/${id}`);
  }
  createVoice(payload: VoiceCreate): Observable<AdminVoice> {
    return this.http.post<AdminVoice>(`${this.base}/voices`, payload);
  }
  updateVoice(id: string, payload: VoiceUpdate): Observable<AdminVoice> {
    return this.http.patch<AdminVoice>(`${this.base}/voices/${id}`, payload);
  }
  activateVoice(id: string): Observable<AdminVoice> {
    return this.http.post<AdminVoice>(`${this.base}/voices/${id}/activate`, {});
  }
  deactivateVoice(id: string): Observable<AdminVoice> {
    return this.http.post<AdminVoice>(`${this.base}/voices/${id}/deactivate`, {});
  }

  getPlanVoices(planId: string): Observable<PlanVoices> {
    return this.http.get<PlanVoices>(`${this.base}/plans/${planId}/voices`);
  }
  setPlanVoices(planId: string, voiceIds: string[]): Observable<PlanVoices> {
    return this.http.put<PlanVoices>(`${this.base}/plans/${planId}/voices`, { voice_ids: voiceIds });
  }

  generatePreview(payload: AdminTtsPreviewRequest): Observable<AdminTtsPreviewResponse> {
    return this.http.post<AdminTtsPreviewResponse>(`${this.base}/tts/preview`, payload);
  }
}
