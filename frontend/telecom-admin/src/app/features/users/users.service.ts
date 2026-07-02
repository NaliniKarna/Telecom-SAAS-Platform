import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  CompanyUser,
  PagedResponse,
  UserInvite,
  UserListItem,
  UserStatus,
  UserUpdate,
} from './user.models';

@Injectable({ providedIn: 'root' })
export class UsersService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = `${environment.apiBaseUrl}/users`;

  list(opts: {
    page?: number; size?: number; search?: string;
    status?: UserStatus; role?: string;
    sortBy?: string; sortDir?: 'asc' | 'desc';
  } = {}): Observable<PagedResponse<UserListItem>> {
    let params = new HttpParams()
      .set('page', opts.page ?? 1)
      .set('size', opts.size ?? 20)
      .set('sort_by', opts.sortBy ?? 'created_at')
      .set('sort_dir', opts.sortDir ?? 'desc');
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    if (opts.role) params = params.set('role', opts.role);
    return this.http.get<PagedResponse<UserListItem>>(this.baseUrl, { params });
  }

  get(id: string): Observable<CompanyUser> {
    return this.http.get<CompanyUser>(`${this.baseUrl}/${id}`);
  }

  invite(payload: UserInvite): Observable<CompanyUser> {
    return this.http.post<CompanyUser>(this.baseUrl, payload);
  }

  update(id: string, payload: UserUpdate): Observable<CompanyUser> {
    return this.http.patch<CompanyUser>(`${this.baseUrl}/${id}`, payload);
  }

  activate(id: string): Observable<CompanyUser> {
    return this.http.post<CompanyUser>(`${this.baseUrl}/${id}/activate`, {});
  }

  deactivate(id: string): Observable<CompanyUser> {
    return this.http.post<CompanyUser>(`${this.baseUrl}/${id}/deactivate`, {});
  }

  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.baseUrl}/${id}`);
  }

  // Public (pre-auth): invitee sets their password.
  acceptInvite(token: string, password: string): Observable<CompanyUser> {
    return this.http.post<CompanyUser>(`${this.baseUrl}/accept-invite`, { token, password });
  }
}
