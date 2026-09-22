import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { PendingRegistration } from './registration.models';

@Injectable({ providedIn: 'root' })
export class RegistrationService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/registration`;

  listPending(): Observable<PendingRegistration[]> {
    return this.http.get<PendingRegistration[]>(`${this.base}/pending`);
  }

  approve(companyId: string): Observable<PendingRegistration> {
    return this.http.post<PendingRegistration>(`${this.base}/${companyId}/approve`, {});
  }

  reject(companyId: string, reason?: string): Observable<PendingRegistration> {
    return this.http.post<PendingRegistration>(`${this.base}/${companyId}/reject`, { reason: reason ?? null });
  }
}
