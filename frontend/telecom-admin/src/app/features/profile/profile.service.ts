import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { CurrentUser } from '../../core/models/auth.models';

export interface ProfileUpdate {
  first_name?: string | null;
  last_name?: string | null;
}

@Injectable({ providedIn: 'root' })
export class ProfileService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/auth`;

  updateProfile(payload: ProfileUpdate): Observable<CurrentUser> {
    return this.http.patch<CurrentUser>(`${this.base}/me`, payload);
  }

  uploadAvatar(file: File): Observable<CurrentUser> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<CurrentUser>(`${this.base}/me/avatar`, form);
  }

  changePassword(currentPassword: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${this.base}/change-password`, {
      current_password: currentPassword,
      new_password: newPassword,
    });
  }
}
