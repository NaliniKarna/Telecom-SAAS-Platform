import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

import { environment } from '../../../environments/environment';
import {
  Contact, ContactCreate, ContactListItem, ContactStatus, ContactUpdate, Paginated,
  ImportPreview, ImportCommitRow, ImportResult,
} from './contact.models';

@Injectable({ providedIn: 'root' })
export class ContactService {
  private readonly http = inject(HttpClient);
  private readonly base = `${environment.apiBaseUrl}/contacts`;

  list(opts: { search?: string; status?: ContactStatus | null; tag?: string | null; page?: number; size?: number } = {}): Observable<Paginated<ContactListItem>> {
    let params = new HttpParams();
    if (opts.search) params = params.set('search', opts.search);
    if (opts.status) params = params.set('status', opts.status);
    if (opts.tag) params = params.set('tag', opts.tag);
    params = params.set('page', String(opts.page ?? 1)).set('size', String(opts.size ?? 20));
    return this.http.get<Paginated<ContactListItem>>(this.base, { params });
  }
  get(id: string): Observable<Contact> { return this.http.get<Contact>(`${this.base}/${id}`); }
  create(payload: ContactCreate): Observable<Contact> { return this.http.post<Contact>(this.base, payload); }
  update(id: string, payload: ContactUpdate): Observable<Contact> { return this.http.patch<Contact>(`${this.base}/${id}`, payload); }
  remove(id: string): Observable<void> { return this.http.delete<void>(`${this.base}/${id}`); }

  importPreview(file: File): Observable<ImportPreview> {
    const form = new FormData();
    form.append('file', file);
    return this.http.post<ImportPreview>(`${this.base}/import/preview`, form);
  }
  importCommit(rows: ImportCommitRow[], onDuplicate: 'skip' | 'import_anyway'): Observable<ImportResult> {
    return this.http.post<ImportResult>(`${this.base}/import`, { rows, on_duplicate: onDuplicate });
  }
}
