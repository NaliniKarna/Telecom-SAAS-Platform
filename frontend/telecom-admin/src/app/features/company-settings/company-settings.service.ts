import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CompanySettings, CompanySettingsUpdate, PendingChangeRequest, SettingsUpdateResult } from './company-settings.models';

@Injectable({ providedIn: 'root' })
export class CompanySettingsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/company-settings`;

  get(): Observable<CompanySettings> {
    return this.http.get<CompanySettings>(this.baseUrl);
  }

  update(payload: CompanySettingsUpdate): Observable<SettingsUpdateResult> {
    return this.http.patch<SettingsUpdateResult>(this.baseUrl, payload);
  }

  pending(): Observable<PendingChangeRequest | null> {
    return this.http.get<PendingChangeRequest | null>(`${this.baseUrl}/pending`);
  }

  uploadLogo(file: File): Observable<CompanySettings> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<CompanySettings>(`${this.baseUrl}/logo`, form);
  }
}
