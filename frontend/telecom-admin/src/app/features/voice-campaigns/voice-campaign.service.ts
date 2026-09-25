import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Paginated, TtsUsageSummary, VoiceCampaign, VoiceCampaignCreate,
  VoiceCampaignEstimate, VoiceCampaignListItem, VoiceCampaignRecipient,
  VoiceCampaignRecipientStatus, VoiceCampaignStatus, VoiceCampaignUpdate,
} from './voice-campaign.models';

@Injectable({ providedIn: 'root' })
export class VoiceCampaignService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/voice-campaigns`;

  listCampaigns(opts: {
    search?: string; status?: VoiceCampaignStatus | null; page?: number; size?: number;
  } = {}): Observable<Paginated<VoiceCampaignListItem>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<VoiceCampaignListItem>>(this.base, { params });
  }

  getCampaign(id: string): Observable<VoiceCampaign> {
    return this.http.get<VoiceCampaign>(`${this.base}/${id}`);
  }

  createCampaign(payload: VoiceCampaignCreate): Observable<VoiceCampaign> {
    return this.http.post<VoiceCampaign>(this.base, payload);
  }

  updateCampaign(id: string, payload: VoiceCampaignUpdate): Observable<VoiceCampaign> {
    return this.http.patch<VoiceCampaign>(`${this.base}/${id}`, payload);
  }

  deleteCampaign(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }

  estimate(id: string): Observable<VoiceCampaignEstimate> {
    return this.http.get<VoiceCampaignEstimate>(`${this.base}/${id}/estimate`);
  }

  startCampaign(id: string): Observable<VoiceCampaign> {
    return this.http.post<VoiceCampaign>(`${this.base}/${id}/start`, {});
  }

  cancelCampaign(id: string): Observable<VoiceCampaign> {
    return this.http.post<VoiceCampaign>(`${this.base}/${id}/cancel`, {});
  }

  campaignRecipients(
    id: string,
    opts: { status?: VoiceCampaignRecipientStatus | null; page?: number; size?: number } = {},
  ): Observable<Paginated<VoiceCampaignRecipient>> {
    let params = new HttpParams();
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 50));
    return this.http.get<Paginated<VoiceCampaignRecipient>>(`${this.base}/${id}/recipients`, { params });
  }

  retryRecipient(campaignId: string, recipientId: string): Observable<VoiceCampaignRecipient> {
    return this.http.post<VoiceCampaignRecipient>(
      `${this.base}/${campaignId}/recipients/${recipientId}/retry`, {},
    );
  }

  usageSummary(): Observable<TtsUsageSummary> {
    return this.http.get<TtsUsageSummary>(`${this.base}/usage/summary`);
  }
}
