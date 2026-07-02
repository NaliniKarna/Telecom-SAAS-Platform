import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog } from '@angular/material/dialog';

import { SmsService } from './sms.service';
import { SmsTemplate, TemplateStatus } from './sms.models';
import { SmsTemplateEditDialogComponent } from './sms-template-edit-dialog.component';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-template-list',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatMenuModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatPaginatorModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>SMS Templates</h1><p>Reusable message bodies with {{ placeholderHint }} placeholders.</p></div>
      <button mat-flat-button color="primary" (click)="create()"><mat-icon>add</mat-icon> New template</button>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline" class="search">
        <mat-icon matPrefix>search</mat-icon>
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="applyFilters()" placeholder="Name or body" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
        </mat-select>
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>description</mat-icon><p>No templates match your filters.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let t"><strong>{{ t.name }}</strong><div class="body">{{ t.body }}</div></td>
          </ng-container>
          <ng-container matColumnDef="variables">
            <th mat-header-cell *matHeaderCellDef>Variables</th>
            <td mat-cell *matCellDef="let t">
              @if (t.variables.length === 0) { <span class="sub">none</span> }
              @for (v of t.variables; track v) { <span class="tag">{{ v }}</span> }
            </td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let t"><span class="chip chip--{{ t.status }}">{{ t.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="updated">
            <th mat-header-cell *matHeaderCellDef>Updated</th>
            <td mat-cell *matCellDef="let t">{{ t.updated_at | date: 'mediumDate' }}</td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let t">
              <button mat-icon-button [matMenuTriggerFor]="menu"><mat-icon>more_vert</mat-icon></button>
              <mat-menu #menu="matMenu">
                <button mat-menu-item (click)="edit(t)"><mat-icon>edit</mat-icon> Edit</button>
                <button mat-menu-item (click)="duplicate(t)"><mat-icon>content_copy</mat-icon> Duplicate</button>
                <button mat-menu-item (click)="remove(t)"><mat-icon>delete</mat-icon> Delete</button>
              </mat-menu>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
        <mat-paginator [length]="total()" [pageSize]="size" [pageIndex]="page - 1"
          [pageSizeOptions]="[10, 20, 50]" (page)="onPage($event)" />
      </mat-card>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; gap: 1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); }
    .filters { display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; } .filters .search { flex: 1 1 280px; }
    table { width: 100%; }
    .body { color: var(--mat-sys-on-surface-variant); font-size: .8rem; max-width: 360px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    .sub { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; font-family: monospace; margin-right: .3rem; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--inactive { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class SmsTemplateListComponent {
  private readonly api = inject(SmsService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly cols = ['name', 'variables', 'status', 'updated', 'actions'];
  readonly placeholderHint = '{{name}}, {{phone}}, {{company}}';
  readonly rows = signal<SmsTemplate[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  search = '';
  statusFilter: TemplateStatus | null = null;
  page = 1;
  size = 20;

  constructor() { this.load(); }
  load(): void {
    this.loading.set(true);
    this.api.listTemplates({ search: this.search || undefined, status: this.statusFilter, page: this.page, size: this.size }).subscribe({
      next: (res) => { this.rows.set(res.data); this.total.set(res.meta.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load templates.'); },
    });
  }
  applyFilters(): void { this.page = 1; this.load(); }
  onPage(e: PageEvent): void { this.page = e.pageIndex + 1; this.size = e.pageSize; this.load(); }

  create(): void {
    this.dialog.open(SmsTemplateEditDialogComponent, { autoFocus: false }).afterClosed().subscribe((t) => { if (t) this.load(); });
  }
  edit(t: SmsTemplate): void {
    this.dialog.open(SmsTemplateEditDialogComponent, { autoFocus: false, data: { template: t } }).afterClosed().subscribe((u) => { if (u) this.load(); });
  }
  duplicate(t: SmsTemplate): void {
    this.api.duplicateTemplate(t.id).subscribe({ next: () => { this.notify.success('Template duplicated.'); this.load(); }, error: () => this.notify.error('Unable to duplicate.') });
  }
  remove(t: SmsTemplate): void {
    const data: ConfirmDialogData = {
      title: 'Delete template',
      message: `Delete "${t.name}"? This cannot be undone from the UI.`,
      confirmText: 'Delete', destructive: true,
    };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.api.deleteTemplate(t.id).subscribe({ next: () => { this.notify.success('Template deleted.'); this.load(); }, error: () => this.notify.error('Unable to delete.') });
    });
  }
}
