import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Company,
  CompanyCreate,
  CompanyListItem,
  CompanyStatus,
  CompanyUpdate,
  PagedResponse,
  SubscriptionPlan,
} from './company.models';

@Injectable({ providedIn: 'root' })
export class CompaniesService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/companies`;

  list(opts: {
    page?: number;
    size?: number;
    search?: string;
    status?: CompanyStatus;
    planId?: string;
    sortBy?: string;
    sortDir?: 'asc' | 'desc';
  } = {}): Observable<PagedResponse<CompanyListItem>> {
    let params = new HttpParams()
      .set('page', opts.page ?? 1)
      .set('size', opts.size ?? 20)
      .set('sort_by', opts.sortBy ?? 'created_at')
      .set('sort_dir', opts.sortDir ?? 'desc');
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    if (opts.planId) params = params.set('plan_id', opts.planId);
    return this.http.get<PagedResponse<CompanyListItem>>(this.baseUrl, { params });
  }

  get(id: string): Observable<Company> {
    return this.http.get<Company>(`${this.baseUrl}/${id}`);
  }

  listPlans(): Observable<SubscriptionPlan[]> {
    return this.http.get<SubscriptionPlan[]>(`${this.baseUrl}/plans`);
  }

  create(payload: CompanyCreate): Observable<Company> {
    return this.http.post<Company>(this.baseUrl, payload);
  }

  update(id: string, payload: CompanyUpdate): Observable<Company> {
    return this.http.patch<Company>(`${this.baseUrl}/${id}`, payload);
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  activate(id: string): Observable<Company> {
    return this.http.post<Company>(`${this.baseUrl}/${id}/activate`, {});
  }

  deactivate(id: string): Observable<Company> {
    return this.http.post<Company>(`${this.baseUrl}/${id}/deactivate`, {});
  }

  inviteAdmin(
    id: string,
    payload: { email: string; first_name?: string | null; last_name?: string | null },
  ): Observable<unknown> {
    return this.http.post(`${this.baseUrl}/${id}/invite-admin`, payload);
  }

  suspend(id: string): Observable<Company> {
    return this.http.post<Company>(`${this.baseUrl}/${id}/suspend`, {});
  }
}
