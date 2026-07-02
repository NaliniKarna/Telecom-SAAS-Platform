import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  AuditFacets,
  AuditLog,
  AuditQuery,
  PagedResponse,
} from './audit.models';

@Injectable({ providedIn: 'root' })
export class AuditService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/audit-logs`;

  list(q: AuditQuery = {}): Observable<PagedResponse<AuditLog>> {
    let params = new HttpParams()
      .set('page', q.page ?? 1)
      .set('size', q.size ?? 25)
      .set('sort_dir', q.sort_dir ?? 'desc');
    if (q.search) params = params.set('search', q.search);
    if (q.company_id) params = params.set('company_id', q.company_id);
    if (q.actor_id) params = params.set('actor_id', q.actor_id);
    if (q.action) params = params.set('action', q.action);
    if (q.entity_type) params = params.set('entity_type', q.entity_type);
    if (q.date_from) params = params.set('date_from', q.date_from);
    if (q.date_to) params = params.set('date_to', q.date_to);
    return this.http.get<PagedResponse<AuditLog>>(this.baseUrl, { params });
  }

  facets(): Observable<AuditFacets> {
    return this.http.get<AuditFacets>(`${this.baseUrl}/facets`);
  }
}
