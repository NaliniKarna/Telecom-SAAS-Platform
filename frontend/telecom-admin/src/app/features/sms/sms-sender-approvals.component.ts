import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';

import { SmsService } from './sms.service';
import { SmsSenderReviewItem } from './sms.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-reject-dialog',
  standalone: true,
  imports: [FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Reject sender ID</h2>
    <mat-dialog-content>
      <p class="muted">Provide a reason the requesting company will see.</p>
      <mat-form-field appearance="outline" style="width: 380px;">
        <mat-label>Reason</mat-label>
        <textarea matInput rows="3" [(ngModel)]="reason"></textarea>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(undefined)">Cancel</button>
      <button mat-flat-button color="warn" (click)="ref.close(reason)">Reject</button>
    </mat-dialog-actions>
  `,
  styles: [`.muted { color: var(--mat-sys-on-surface-variant); margin: 0 0 .5rem; }`],
})
export class SmsRejectDialogComponent {
  readonly ref = inject(MatDialogRef<SmsRejectDialogComponent>);
  reason = '';
}

@Component({
  selector: 'app-sms-sender-approvals',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatPaginatorModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>Sender ID Approvals</h1><p>Review pending sender IDs requested by companies across the platform.</p></div>
    </header>
    <div class="filters">
      <mat-form-field appearance="outline" class="search">
        <mat-icon matPrefix>search</mat-icon>
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="applyFilters()" placeholder="Name or sender ID" />
      </mat-form-field>
    </div>
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>task_alt</mat-icon><p>No sender IDs awaiting review.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="company">
            <th mat-header-cell *matHeaderCellDef>Company</th>
            <td mat-cell *matCellDef="let r">{{ r.company_name || '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="sender_id">
            <th mat-header-cell *matHeaderCellDef>Sender ID</th>
            <td mat-cell *matCellDef="let r"><strong>{{ r.sender_id }}</strong><div class="sub">{{ r.name }}</div></td>
          </ng-container>
          <ng-container matColumnDef="description">
            <th mat-header-cell *matHeaderCellDef>Description</th>
            <td mat-cell *matCellDef="let r" class="desc">{{ r.description || '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="requested">
            <th mat-header-cell *matHeaderCellDef>Requested</th>
            <td mat-cell *matCellDef="let r">{{ r.created_at | date: 'medium' }}</td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let r">
              <button mat-flat-button color="primary" (click)="approve(r)">Approve</button>
              <button mat-stroked-button color="warn" (click)="reject(r)">Reject</button>
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
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0 0 1rem; color: var(--mat-sys-on-surface-variant); }
    .filters .search { width: 340px; max-width: 100%; }
    table { width: 100%; } .sub { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .desc { max-width: 280px; white-space: normal; color: var(--mat-sys-on-surface-variant); }
    td button { margin-right: .5rem; }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class SmsSenderApprovalsComponent {
  private readonly api = inject(SmsService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly cols = ['company', 'sender_id', 'description', 'requested', 'actions'];
  readonly rows = signal<SmsSenderReviewItem[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  search = '';
  page = 1;
  size = 20;

  constructor() { this.load(); }
  load(): void {
    this.loading.set(true);
    this.api.listPendingSenderIds({ search: this.search || undefined, page: this.page, size: this.size }).subscribe({
      next: (res) => { this.rows.set(res.data); this.total.set(res.meta.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load pending sender IDs.'); },
    });
  }
  applyFilters(): void { this.page = 1; this.load(); }
  onPage(e: PageEvent): void { this.page = e.pageIndex + 1; this.size = e.pageSize; this.load(); }

  approve(r: SmsSenderReviewItem): void {
    this.api.approveSenderId(r.id).subscribe({ next: () => { this.notify.success(`Approved ${r.sender_id}.`); this.load(); }, error: () => this.notify.error('Unable to approve.') });
  }
  reject(r: SmsSenderReviewItem): void {
    this.dialog.open(SmsRejectDialogComponent, { autoFocus: false }).afterClosed().subscribe((reason: string | undefined) => {
      if (reason === undefined) return;
      this.api.rejectSenderId(r.id, reason || null).subscribe({ next: () => { this.notify.success(`Rejected ${r.sender_id}.`); this.load(); }, error: () => this.notify.error('Unable to reject.') });
    });
  }
}
