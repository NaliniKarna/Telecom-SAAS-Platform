import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  CallbackRequest,
  MissedCallCallback,
  MissedCallCreate,
  MissedCallDashboardStats,
  MissedCallDetail,
  MissedCallNote,
  MissedCallRead,
  PaginatedMissedCalls,
} from './missed-call.models';

@Injectable({ providedIn: 'root' })
export class MissedCallService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/missed-calls`;

  // ── List / Create ──

  list(opts: {
    offset?: number;
    limit?: number;
    status?: string | null;
    assigned_to?: string | null;
    search?: string | null;
    from_date?: string | null;
    to_date?: string | null;
  } = {}): Observable<PaginatedMissedCalls> {
    let params = new HttpParams();
    if (opts.offset != null) params = params.set('offset', String(opts.offset));
    if (opts.limit != null) params = params.set('limit', String(opts.limit));
    if (opts.status) params = params.set('status', opts.status);
    if (opts.assigned_to) params = params.set('assigned_to', opts.assigned_to);
    if (opts.search) params = params.set('search', opts.search);
    if (opts.from_date) params = params.set('from_date', opts.from_date);
    if (opts.to_date) params = params.set('to_date', opts.to_date);
    return this.http.get<PaginatedMissedCalls>(this.base, { params });
  }

  create(data: MissedCallCreate): Observable<MissedCallRead> {
    return this.http.post<MissedCallRead>(this.base, data);
  }

  // ── Detail / Status / Assignment ──

  get(id: string): Observable<MissedCallDetail> {
    return this.http.get<MissedCallDetail>(`${this.base}/${id}`);
  }

  updateStatus(id: string, status: string): Observable<MissedCallRead> {
    return this.http.patch<MissedCallRead>(`${this.base}/${id}/status`, { status });
  }

  assign(id: string, assigned_to: string | null): Observable<MissedCallRead> {
    return this.http.patch<MissedCallRead>(`${this.base}/${id}/assign`, { assigned_to });
  }

  // ── Notes ──

  addNote(id: string, body: string): Observable<MissedCallNote> {
    return this.http.post<MissedCallNote>(`${this.base}/${id}/notes`, { body });
  }

  // ── Callbacks ──

  initiateCallback(id: string, data: CallbackRequest): Observable<MissedCallCallback> {
    return this.http.post<MissedCallCallback>(`${this.base}/${id}/callbacks`, data);
  }

  updateCallbackOutcome(
    mcId: string,
    cbId: string,
    outcome: string,
    duration_seconds?: number | null,
    notes?: string | null,
  ): Observable<MissedCallCallback> {
    return this.http.patch<MissedCallCallback>(
      `${this.base}/${mcId}/callbacks/${cbId}/outcome`,
      { outcome, ...(duration_seconds != null ? { duration_seconds } : {}), ...(notes ? { notes } : {}) },
    );
  }

  // ── Dashboard ──

  getDashboardStats(): Observable<MissedCallDashboardStats> {
    return this.http.get<MissedCallDashboardStats>(`${this.base}/dashboard/stats`);
  }
}
