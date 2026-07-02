import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatMenuModule } from '@angular/material/menu';
import { MatDialog } from '@angular/material/dialog';

import { ContactService } from './contact.service';
import { ContactListItem, ContactStatus } from './contact.models';
import { ContactEditDialogComponent } from './contact-edit-dialog.component';
import { ContactImportDialogComponent } from './contact-import-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-contact-list',
  standalone: true,
  imports: [
    FormsModule, MatCardModule, MatTableModule, MatButtonModule,
    MatIconModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatChipsModule, MatProgressBarModule, MatMenuModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Contacts</h1>
        <p>Manage your contacts. Mobile numbers are normalized to +977 automatically.</p>
      </div>
      <div class="header-actions">
        <button mat-stroked-button (click)="importCsv()"><mat-icon>upload_file</mat-icon> Import CSV</button>
        <button mat-flat-button color="primary" (click)="create()"><mat-icon>add</mat-icon> New contact</button>
      </div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="load()" placeholder="Name, email, number" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="status" (selectionChange)="load()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
          <mat-option value="unsubscribed">Unsubscribed</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Tag</mat-label>
        <input matInput [(ngModel)]="tag" (keyup.enter)="load()" placeholder="e.g. vip" />
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>contacts</mat-icon><p>No contacts found. Add your first contact.</p></div>
    }

    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let c">{{ fullName(c) }}</td>
          </ng-container>
          <ng-container matColumnDef="mobile">
            <th mat-header-cell *matHeaderCellDef>Mobile</th>
            <td mat-cell *matCellDef="let c">{{ c.mobile_e164 ?? '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="email">
            <th mat-header-cell *matHeaderCellDef>Email</th>
            <td mat-cell *matCellDef="let c">{{ c.email ?? '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="tags">
            <th mat-header-cell *matHeaderCellDef>Tags</th>
            <td mat-cell *matCellDef="let c">
              @for (t of c.tags; track t) { <span class="tag">{{ t }}</span> }
            </td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let c"><span class="chip chip--{{ c.status }}">{{ c.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let c">
              <button mat-icon-button [matMenuTriggerFor]="menu" aria-label="Actions"><mat-icon>more_vert</mat-icon></button>
              <mat-menu #menu="matMenu">
                <button mat-menu-item (click)="edit(c)"><mat-icon>edit</mat-icon><span>Edit</span></button>
                <button mat-menu-item (click)="remove(c)"><mat-icon>delete</mat-icon><span>Delete</span></button>
              </mat-menu>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
      </mat-card>
    }
  `,
  styles: [
    `
      .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .header-actions { display: flex; gap: 0.5rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .filters { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }
      .filters mat-form-field { min-width: 180px; }
      table { width: 100%; }
      .tag { display: inline-block; background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container);
        padding: 0.1rem 0.5rem; border-radius: 999px; font-size: 0.75rem; margin: 0 0.2rem 0.2rem 0; }
      .chip { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .chip--inactive { background: var(--mat-sys-surface-container-highest); color: var(--mat-sys-on-surface-variant); }
      .chip--unsubscribed { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
    `,
  ],
})
export class ContactListComponent {
  private readonly api = inject(ContactService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly cols = ['name', 'mobile', 'email', 'tags', 'status', 'actions'];
  readonly rows = signal<ContactListItem[]>([]);
  readonly loading = signal(false);
  search = '';
  status: ContactStatus | null = null;
  tag = '';

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.list({ search: this.search, status: this.status, tag: this.tag }).subscribe({
      next: (res) => { this.rows.set(res.data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  fullName(c: ContactListItem): string {
    return [c.first_name, c.last_name].filter(Boolean).join(' ') || '—';
  }

  importCsv(): void {
    this.dialog.open(ContactImportDialogComponent, { autoFocus: false, maxWidth: '760px' })
      .afterClosed().subscribe((done) => { if (done) this.load(); });
  }

  create(): void {
    this.dialog.open(ContactEditDialogComponent, { data: null, autoFocus: false })
      .afterClosed().subscribe((c) => { if (c) this.load(); });
  }

  edit(c: ContactListItem): void {
    // fetch full record first (list item is partial)
    this.api.get(c.id).subscribe((full) => {
      this.dialog.open(ContactEditDialogComponent, { data: full, autoFocus: false })
        .afterClosed().subscribe((updated) => { if (updated) this.load(); });
    });
  }

  remove(c: ContactListItem): void {
    this.api.remove(c.id).subscribe({
      next: () => { this.notify.success('Contact deleted.'); this.load(); },
    });
  }
}
