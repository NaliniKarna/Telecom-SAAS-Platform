import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  ConnectionTestResult,
  TelephonyConnection,
  TelephonyConnectionCreate,
  TelephonyConnectionUpdate,
} from './telephony.models';

/**
 * Wraps the /telephony endpoints. All are super-admin-only on the backend
 * (provider-managed PBX infrastructure); the UI is gated to super admins too.
 */
@Injectable({ providedIn: 'root' })
export class TelephonyService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/telephony`;

  listConnections(): Observable<TelephonyConnection[]> {
    return this.http.get<TelephonyConnection[]>(`${this.base}/connections`);
  }

  createConnection(
    payload: TelephonyConnectionCreate,
  ): Observable<TelephonyConnection> {
    return this.http.post<TelephonyConnection>(
      `${this.base}/connections`,
      payload,
    );
  }

  updateConnection(
    id: string,
    payload: TelephonyConnectionUpdate,
  ): Observable<TelephonyConnection> {
    return this.http.patch<TelephonyConnection>(
      `${this.base}/connections/${id}`,
      payload,
    );
  }

  deleteConnection(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/connections/${id}`);
  }

  /** Probe a connection and persist its last_status. */
  testConnection(id: string): Observable<ConnectionTestResult> {
    return this.http.post<ConnectionTestResult>(
      `${this.base}/connections/${id}/test`,
      {},
    );
  }
}
