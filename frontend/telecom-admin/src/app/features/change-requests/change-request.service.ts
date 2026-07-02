import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ChangeRequest, RecentActivity } from './change-request.models';

@Injectable({ providedIn: 'root' })
export class ChangeRequestService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/change-requests`;

  listPending(): Observable<ChangeRequest[]> {
    return this.http.get<ChangeRequest[]>(this.base);
  }

  approve(id: string): Observable<ChangeRequest> {
    return this.http.post<ChangeRequest>(`${this.base}/${id}/approve`, {});
  }

  reject(id: string, reason: string | null): Observable<ChangeRequest> {
    return this.http.post<ChangeRequest>(`${this.base}/${id}/reject`, { reason });
  }

  recentActivity(): Observable<RecentActivity[]> {
    return this.http.get<RecentActivity[]>(`${this.base}/recent-activity`);
  }
}
