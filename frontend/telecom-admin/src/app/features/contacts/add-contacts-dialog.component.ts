import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { ContactService } from './contact.service';
import { ContactListItem } from './contact.models';

@Component({
  selector: 'app-add-contacts-dialog',
  standalone: true,
  imports: [FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule, MatCheckboxModule, MatProgressBarModule],
  template: `
    <h2 mat-dialog-title>Add contacts</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Search contacts</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="load()" placeholder="Name, email, number" />
      </mat-form-field>
      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
      <div class="list">
        @for (c of candidates(); track c.id) {
          <label class="row">
            <mat-checkbox [checked]="selected().has(c.id)" (change)="toggle(c.id)" [disabled]="data.existing.includes(c.id)" />
            <span class="row__name">{{ name(c) }}</span>
            <span class="row__sub">{{ c.mobile_e164 ?? c.email ?? '' }}</span>
            @if (data.existing.includes(c.id)) { <span class="row__tag">already in list</span> }
          </label>
        } @empty { @if (!loading()) { <p class="muted">No contacts found.</p> } }
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="primary" (click)="confirm()" [disabled]="selected().size === 0">Add {{ selected().size || '' }}</button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .full { width: 100%; min-width: 440px; }
      .list { max-height: 320px; overflow: auto; }
      .row { display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; }
      .row__name { font-weight: 500; }
      .row__sub { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .row__tag { margin-left: auto; color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-label-small); }
      .muted { color: var(--mat-sys-on-surface-variant); }
    `,
  ],
})
export class AddContactsDialogComponent {
  private readonly api = inject(ContactService);
  readonly ref = inject(MatDialogRef<AddContactsDialogComponent>);
  readonly data = inject<{ existing: string[] }>(MAT_DIALOG_DATA);
  readonly candidates = signal<ContactListItem[]>([]);
  readonly selected = signal<Set<string>>(new Set());
  readonly loading = signal(false);
  search = '';

  constructor() { this.load(); }
  load(): void {
    this.loading.set(true);
    this.api.list({ search: this.search, size: 50 }).subscribe({
      next: (res) => { this.candidates.set(res.data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
  name(c: ContactListItem): string { return [c.first_name, c.last_name].filter(Boolean).join(' ') || c.email || c.mobile_e164 || 'Contact'; }
  toggle(id: string): void {
    this.selected.update((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  }
  confirm(): void { this.ref.close(Array.from(this.selected())); }
}
