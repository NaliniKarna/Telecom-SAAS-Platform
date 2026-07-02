import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ApiKey, ApiKeyCreate, ApiKeyCreated, Paginated } from './api-key.models';

@Injectable({ providedIn: 'root' })
export class ApiKeyService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/api-keys`;

  list(page = 1, size = 20): Observable<Paginated<ApiKey>> {
    const params = new HttpParams().set('page', page).set('size', size);
    return this.http.get<Paginated<ApiKey>>(this.base, { params });
  }
  generate(payload: ApiKeyCreate): Observable<ApiKeyCreated> {
    return this.http.post<ApiKeyCreated>(this.base, payload);
  }
  revoke(id: string): Observable<ApiKey> {
    return this.http.post<ApiKey>(`${this.base}/${id}/revoke`, {});
  }
}
