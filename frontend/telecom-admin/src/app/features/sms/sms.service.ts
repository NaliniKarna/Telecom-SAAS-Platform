import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Paginated, SenderApprovalStatus, SenderIdCreate, SenderIdUpdate, SenderStatus,
  SmsSenderId, SmsSenderReviewItem, SmsTemplate, TemplateCreate, TemplatePreview,
  TemplateStatus, TemplateUpdate,
  SmsCampaign, SmsCampaignListItem, CampaignCreate, CampaignUpdate,
  CampaignRecipient, CampaignMessage, CampaignStatus, MessageStatus,
  AnalyticsOverview, AnalyticsTimePoint, AnalyticsFilters,
} from './sms.models';

@Injectable({ providedIn: 'root' })
export class SmsService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/sms`;

  // ---- Sender IDs (company admin) ----
  listSenderIds(opts: {
    search?: string; status?: SenderStatus | null;
    approval_status?: SenderApprovalStatus | null; page?: number; size?: number;
  } = {}): Observable<Paginated<SmsSenderId>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    if (opts.approval_status) params = params.set('approval_status', opts.approval_status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<SmsSenderId>>(`${this.base}/sender-ids`, { params });
  }
  getSenderId(id: string): Observable<SmsSenderId> {
    return this.http.get<SmsSenderId>(`${this.base}/sender-ids/${id}`);
  }
  createSenderId(payload: SenderIdCreate): Observable<SmsSenderId> {
    return this.http.post<SmsSenderId>(`${this.base}/sender-ids`, payload);
  }
  updateSenderId(id: string, payload: SenderIdUpdate): Observable<SmsSenderId> {
    return this.http.patch<SmsSenderId>(`${this.base}/sender-ids/${id}`, payload);
  }
  setDefaultSenderId(id: string): Observable<SmsSenderId> {
    return this.http.post<SmsSenderId>(`${this.base}/sender-ids/${id}/set-default`, {});
  }
  activateSenderId(id: string): Observable<SmsSenderId> {
    return this.http.post<SmsSenderId>(`${this.base}/sender-ids/${id}/activate`, {});
  }
  deactivateSenderId(id: string): Observable<SmsSenderId> {
    return this.http.post<SmsSenderId>(`${this.base}/sender-ids/${id}/deactivate`, {});
  }

  // ---- Sender ID approval (super admin) ----
  listPendingSenderIds(opts: { search?: string; page?: number; size?: number } = {}): Observable<Paginated<SmsSenderReviewItem>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<SmsSenderReviewItem>>(`${this.base}/sender-ids/pending`, { params });
  }
  approveSenderId(id: string): Observable<SmsSenderId> {
    return this.http.post<SmsSenderId>(`${this.base}/sender-ids/${id}/approve`, {});
  }
  rejectSenderId(id: string, reason: string | null): Observable<SmsSenderId> {
    return this.http.post<SmsSenderId>(`${this.base}/sender-ids/${id}/reject`, { reason });
  }

  // ---- Templates (company admin) ----
  listTemplates(opts: {
    search?: string; status?: TemplateStatus | null; page?: number; size?: number;
  } = {}): Observable<Paginated<SmsTemplate>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<SmsTemplate>>(`${this.base}/templates`, { params });
  }
  getTemplate(id: string): Observable<SmsTemplate> {
    return this.http.get<SmsTemplate>(`${this.base}/templates/${id}`);
  }
  createTemplate(payload: TemplateCreate): Observable<SmsTemplate> {
    return this.http.post<SmsTemplate>(`${this.base}/templates`, payload);
  }
  updateTemplate(id: string, payload: TemplateUpdate): Observable<SmsTemplate> {
    return this.http.patch<SmsTemplate>(`${this.base}/templates/${id}`, payload);
  }
  deleteTemplate(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/templates/${id}`);
  }
  duplicateTemplate(id: string): Observable<SmsTemplate> {
    return this.http.post<SmsTemplate>(`${this.base}/templates/${id}/duplicate`, {});
  }
  previewTemplate(body: string, values: Record<string, string>): Observable<TemplatePreview> {
    return this.http.post<TemplatePreview>(`${this.base}/templates/preview`, { body, values });
  }

  // ----- Campaigns -----
  listCampaigns(opts: {
    search?: string; status?: CampaignStatus | null; page?: number; size?: number;
  } = {}): Observable<Paginated<SmsCampaignListItem>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<SmsCampaignListItem>>(`${this.base}/campaigns`, { params });
  }
  getCampaign(id: string): Observable<SmsCampaign> {
    return this.http.get<SmsCampaign>(`${this.base}/campaigns/${id}`);
  }
  createCampaign(payload: CampaignCreate): Observable<SmsCampaign> {
    return this.http.post<SmsCampaign>(`${this.base}/campaigns`, payload);
  }
  updateCampaign(id: string, payload: CampaignUpdate): Observable<SmsCampaign> {
    return this.http.patch<SmsCampaign>(`${this.base}/campaigns/${id}`, payload);
  }
  scheduleCampaign(id: string, scheduleTime: string): Observable<SmsCampaign> {
    return this.http.post<SmsCampaign>(`${this.base}/campaigns/${id}/schedule`, { schedule_time: scheduleTime });
  }
  sendCampaign(id: string): Observable<SmsCampaign> {
    return this.http.post<SmsCampaign>(`${this.base}/campaigns/${id}/send`, {});
  }
  cancelCampaign(id: string): Observable<SmsCampaign> {
    return this.http.post<SmsCampaign>(`${this.base}/campaigns/${id}/cancel`, {});
  }
  campaignRecipients(id: string, opts: { page?: number; size?: number } = {}): Observable<Paginated<CampaignRecipient>> {
    let params = new HttpParams().set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 50));
    return this.http.get<Paginated<CampaignRecipient>>(`${this.base}/campaigns/${id}/recipients`, { params });
  }
  campaignMessages(id: string, opts: { status?: MessageStatus | null; page?: number; size?: number } = {}): Observable<Paginated<CampaignMessage>> {
    let params = new HttpParams();
    if (opts.status) params = params.set('status', opts.status);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 50));
    return this.http.get<Paginated<CampaignMessage>>(`${this.base}/campaigns/${id}/messages`, { params });
  }

  // ----- Analytics & tracking -----
  private analyticsParams(f: AnalyticsFilters): HttpParams {
    let p = new HttpParams();
    if (f.campaign_id) p = p.set('campaign_id', f.campaign_id);
    if (f.sender_id) p = p.set('sender_id', f.sender_id);
    if (f.since) p = p.set('since', f.since);
    if (f.until) p = p.set('until', f.until);
    return p;
  }
  analyticsOverview(f: AnalyticsFilters = {}): Observable<AnalyticsOverview> {
    return this.http.get<AnalyticsOverview>(`${this.base}/analytics`, { params: this.analyticsParams(f) });
  }
  analyticsTimeseries(f: AnalyticsFilters = {}): Observable<AnalyticsTimePoint[]> {
    return this.http.get<AnalyticsTimePoint[]>(`${this.base}/analytics/timeseries`, { params: this.analyticsParams(f) });
  }
  trackingMessages(f: AnalyticsFilters & { status?: MessageStatus | null; page?: number; size?: number } = {}): Observable<Paginated<CampaignMessage>> {
    let p = this.analyticsParams(f);
    if (f.status) p = p.set('status', f.status);
    p = p.set('page', String(f.page ?? 1)).set('size', String(f.size ?? 50));
    return this.http.get<Paginated<CampaignMessage>>(`${this.base}/messages`, { params: p });
  }
}
