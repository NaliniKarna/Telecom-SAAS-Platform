import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Group, GroupActivity, GroupCreate, GroupListItem, GroupMember,
  GroupStatus, GroupType, GroupUpdate, Paginated,
} from './group.models';

@Injectable({ providedIn: 'root' })
export class GroupService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/groups`;

  list(opts: { search?: string; status?: GroupStatus | null; group_type?: GroupType | null; page?: number; size?: number } = {}): Observable<Paginated<GroupListItem>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    if (opts.group_type) params = params.set('group_type', opts.group_type);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<GroupListItem>>(this.base, { params });
  }

  get(id: string): Observable<Group> {
    return this.http.get<Group>(`${this.base}/${id}`);
  }
  create(payload: GroupCreate): Observable<Group> {
    return this.http.post<Group>(this.base, payload);
  }
  update(id: string, payload: GroupUpdate): Observable<Group> {
    return this.http.patch<Group>(`${this.base}/${id}`, payload);
  }
  remove(id: string): Observable<void> {
    return this.http.delete<void>(`${this.base}/${id}`);
  }
  members(id: string): Observable<GroupMember[]> {
    return this.http.get<GroupMember[]>(`${this.base}/${id}/members`);
  }
  addMembers(id: string, userIds: string[]): Observable<GroupMember[]> {
    return this.http.post<GroupMember[]>(`${this.base}/${id}/members`, { user_ids: userIds });
  }
  removeMember(id: string, userId: string): Observable<GroupMember[]> {
    return this.http.delete<GroupMember[]>(`${this.base}/${id}/members/${userId}`);
  }
  activity(id: string): Observable<GroupActivity[]> {
    return this.http.get<GroupActivity[]>(`${this.base}/${id}/activity`);
  }
}
