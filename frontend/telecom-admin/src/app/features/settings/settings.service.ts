import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { PlatformSettings, PlatformSettingsUpdate } from './settings.models';

@Injectable({ providedIn: 'root' })
export class SettingsService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/platform-settings`;

  get(): Observable<PlatformSettings> {
    return this.http.get<PlatformSettings>(this.baseUrl);
  }

  update(payload: PlatformSettingsUpdate): Observable<PlatformSettings> {
    return this.http.patch<PlatformSettings>(this.baseUrl, payload);
  }
}
