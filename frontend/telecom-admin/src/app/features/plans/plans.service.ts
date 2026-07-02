import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  PagedResponse,
  PlanCreate,
  PlanDetailResponse,
  PlanListItem,
  PlanUpdate,
  SubscriptionPlan,
} from './plan.models';

@Injectable({ providedIn: 'root' })
export class PlansService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/subscription-plans`;

  list(opts: {
    page?: number;
    size?: number;
    search?: string;
    isActive?: boolean;
    sortBy?: string;
    sortDir?: 'asc' | 'desc';
  } = {}): Observable<PagedResponse<PlanListItem>> {
    let params = new HttpParams()
      .set('page', opts.page ?? 1)
      .set('size', opts.size ?? 20)
      .set('sort_by', opts.sortBy ?? 'created_at')
      .set('sort_dir', opts.sortDir ?? 'desc');
    if (opts.search) params = params.set('search', opts.search);
    if (opts.isActive !== undefined) {
      params = params.set('is_active', opts.isActive);
    }
    return this.http.get<PagedResponse<PlanListItem>>(this.baseUrl, { params });
  }

  get(id: string): Observable<PlanDetailResponse> {
    return this.http.get<PlanDetailResponse>(`${this.baseUrl}/${id}`);
  }

  create(payload: PlanCreate): Observable<SubscriptionPlan> {
    return this.http.post<SubscriptionPlan>(this.baseUrl, payload);
  }

  update(id: string, payload: PlanUpdate): Observable<SubscriptionPlan> {
    return this.http.patch<SubscriptionPlan>(`${this.baseUrl}/${id}`, payload);
  }

  activate(id: string): Observable<SubscriptionPlan> {
    return this.http.post<SubscriptionPlan>(`${this.baseUrl}/${id}/activate`, {});
  }

  deactivate(id: string): Observable<SubscriptionPlan> {
    return this.http.post<SubscriptionPlan>(`${this.baseUrl}/${id}/deactivate`, {});
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }
}
