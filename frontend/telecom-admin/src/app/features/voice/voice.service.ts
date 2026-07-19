import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ExtensionStatusSummary,
  OriginateRequest,
  PaginatedCallLogs,
  VoiceCallLog,
  VoiceExtension,
  VoiceExtensionCreate,
  VoiceExtensionUpdate,
  VoiceOverviewStats,
  VoiceTimeseriesStats,
} from './voice.models';

@Injectable({ providedIn: 'root' })
export class VoiceService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/voice`;

  // ── Extensions ──

  listExtensions(opts: {
    offset?: number;
    limit?: number;
  } = {}): Observable<VoiceExtension[]> {
    let params = new HttpParams();
    if (opts.offset != null) params = params.set('offset', String(opts.offset));
    if (opts.limit != null) params = params.set('limit', String(opts.limit));
    return this.http.get<VoiceExtension[]>(`${this.base}/extensions`, { params });
  }

  getExtension(id: string): Observable<VoiceExtension> {
    return this.http.get<VoiceExtension>(`${this.base}/extensions/${id}`);
  }

  createExtension(data: VoiceExtensionCreate): Observable<VoiceExtension> {
    return this.http.post<VoiceExtension>(`${this.base}/extensions`, data);
  }

  updateExtension(id: string, data: VoiceExtensionUpdate): Observable<VoiceExtension> {
    return this.http.patch<VoiceExtension>(`${this.base}/extensions/${id}`, data);
  }

  deleteExtension(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/extensions/${id}`);
  }

  updateAgentStatus(id: string, agent_status: string): Observable<VoiceExtension> {
    return this.http.patch<VoiceExtension>(
      `${this.base}/extensions/${id}/agent-status`,
      { agent_status },
    );
  }

  // ── Calls ──

  listCalls(opts: {
    offset?: number;
    limit?: number;
    direction?: string | null;
    status?: string | null;
    extension_id?: string | null;
    search?: string | null;
    from_date?: string | null;
    to_date?: string | null;
  } = {}): Observable<PaginatedCallLogs> {
    let params = new HttpParams();
    if (opts.offset != null) params = params.set('offset', String(opts.offset));
    if (opts.limit != null) params = params.set('limit', String(opts.limit));
    if (opts.direction) params = params.set('direction', opts.direction);
    if (opts.status) params = params.set('status', opts.status);
    if (opts.extension_id) params = params.set('extension_id', opts.extension_id);
    if (opts.search) params = params.set('search', opts.search);
    if (opts.from_date) params = params.set('from_date', opts.from_date);
    if (opts.to_date) params = params.set('to_date', opts.to_date);
    return this.http.get<PaginatedCallLogs>(`${this.base}/calls`, { params });
  }

  getActiveCalls(): Observable<VoiceCallLog[]> {
    return this.http.get<VoiceCallLog[]>(`${this.base}/calls/active`);
  }

  getCall(id: string): Observable<VoiceCallLog> {
    return this.http.get<VoiceCallLog>(`${this.base}/calls/${id}`);
  }

  originateCall(data: OriginateRequest): Observable<VoiceCallLog> {
    return this.http.post<VoiceCallLog>(`${this.base}/calls/originate`, data);
  }

  updateCallStatus(id: string, status: string, hangup_cause?: string): Observable<VoiceCallLog> {
    return this.http.patch<VoiceCallLog>(
      `${this.base}/calls/${id}/status`,
      { status, ...(hangup_cause ? { hangup_cause } : {}) },
    );
  }

  hangupCall(id: string): Observable<VoiceCallLog> {
    return this.http.post<VoiceCallLog>(`${this.base}/calls/${id}/hangup`, {});
  }

  // ── Analytics ──

  getOverview(): Observable<VoiceOverviewStats> {
    return this.http.get<VoiceOverviewStats>(`${this.base}/analytics/overview`);
  }

  getTimeseries(days: number = 30): Observable<VoiceTimeseriesStats> {
    const params = new HttpParams().set('days', String(days));
    return this.http.get<VoiceTimeseriesStats>(`${this.base}/analytics/timeseries`, { params });
  }

  getExtensionStatusSummary(): Observable<ExtensionStatusSummary> {
    return this.http.get<ExtensionStatusSummary>(`${this.base}/analytics/extension-status`);
  }
}
