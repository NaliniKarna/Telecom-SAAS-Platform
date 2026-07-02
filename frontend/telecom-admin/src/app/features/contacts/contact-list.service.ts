import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import { ContactGroup, ContactGroupMember, Paginated } from './contact.models';

@Injectable({ providedIn: 'root' })
export class ContactListService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/contact-lists`;

  list(search = '', page = 1, size = 20): Observable<Paginated<ContactGroup>> {
    let params = new HttpParams().set('page', page).set('size', size);
    if (search) params = params.set('search', search);
    return this.http.get<Paginated<ContactGroup>>(this.base, { params });
  }
  get(id: string): Observable<ContactGroup> { return this.http.get<ContactGroup>(`${this.base}/${id}`); }
  create(payload: { name: string; description?: string | null }): Observable<ContactGroup> { return this.http.post<ContactGroup>(this.base, payload); }
  update(id: string, payload: { name?: string; description?: string | null }): Observable<ContactGroup> { return this.http.patch<ContactGroup>(`${this.base}/${id}`, payload); }
  remove(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/${id}`); }
  members(id: string): Observable<ContactGroupMember[]> { return this.http.get<ContactGroupMember[]>(`${this.base}/${id}/members`); }
  addContacts(id: string, contactIds: string[]): Observable<ContactGroupMember[]> { return this.http.post<ContactGroupMember[]>(`${this.base}/${id}/members`, { contact_ids: contactIds }); }
  removeContact(id: string, contactId: string): Observable<ContactGroupMember[]> { return this.http.delete<ContactGroupMember[]>(`${this.base}/${id}/members/${contactId}`); }
}
