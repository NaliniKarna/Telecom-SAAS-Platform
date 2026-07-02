import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';

import { SmsService } from './sms.service';
import { SmsSenderId, SenderApprovalStatus, SenderStatus } from './sms.models';
import { SmsSenderCreateDialogComponent } from './sms-sender-create-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-sender-ids',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatMenuModule, MatChipsModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatPaginatorModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>Sender IDs</h1><p>Register the alphanumeric senders your messages are sent from. New IDs need super-admin approval.</p></div>
      <button mat-flat-button color="primary" (click)="create()"><mat-icon>add</mat-icon> Request sender ID</button>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline" class="search">
        <mat-icon matPrefix>search</mat-icon>
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="applyFilters()" placeholder="Name or sender ID" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Approval</mat-label>
        <mat-select [(ngModel)]="approvalFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="pending">Pending</mat-option>
          <mat-option value="approved">Approved</mat-option>
          <mat-option value="rejected">Rejected</mat-option>
        </mat-select>
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
      <div class="empty"><mat-icon>badge</mat-icon><p>No sender IDs match your filters.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="sender_id">
            <th mat-header-cell *matHeaderCellDef>Sender ID</th>
            <td mat-cell *matCellDef="let s">
              <strong>{{ s.sender_id }}</strong>
              @if (s.is_default) { <mat-icon class="default-star" matTooltip="Default sender">star</mat-icon> }
              <div class="sub">{{ s.name }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="approval">
            <th mat-header-cell *matHeaderCellDef>Approval</th>
            <td mat-cell *matCellDef="let s">
              <span class="chip chip--{{ s.approval_status }}">{{ s.approval_status }}</span>
              @if (s.approval_status === 'rejected' && s.rejection_reason) {
                <mat-icon class="reason" [matTooltip]="s.rejection_reason">info</mat-icon>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let s"><span class="chip chip--{{ s.status }}">{{ s.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="created">
            <th mat-header-cell *matHeaderCellDef>Created</th>
            <td mat-cell *matCellDef="let s">{{ s.created_at | date: 'mediumDate' }}</td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let s">
              <button mat-icon-button [matMenuTriggerFor]="menu"><mat-icon>more_vert</mat-icon></button>
              <mat-menu #menu="matMenu">
                <button mat-menu-item (click)="edit(s)"><mat-icon>edit</mat-icon> Edit</button>
                <button mat-menu-item (click)="setDefault(s)" [disabled]="s.approval_status !== 'approved' || s.is_default">
                  <mat-icon>star</mat-icon> Set as default
                </button>
                @if (s.status === 'active') {
                  <button mat-menu-item (click)="deactivate(s)"><mat-icon>block</mat-icon> Deactivate</button>
                } @else {
                  <button mat-menu-item (click)="activate(s)"><mat-icon>check_circle</mat-icon> Activate</button>
                }
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
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); max-width: 48ch; }
    .filters { display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; } .filters .search { flex: 1 1 280px; }
    table { width: 100%; } .sub { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .default-star { color: var(--mat-sys-tertiary); font-size: 1rem; height: 1rem; width: 1rem; vertical-align: middle; }
    .reason { font-size: 1rem; height: 1rem; width: 1rem; vertical-align: middle; color: var(--mat-sys-error); cursor: help; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--approved, .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--pending { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
    .chip--rejected, .chip--inactive { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class SmsSenderIdsComponent {
  private readonly api = inject(SmsService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly cols = ['sender_id', 'approval', 'status', 'created', 'actions'];
  readonly rows = signal<SmsSenderId[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);

  search = '';
  approvalFilter: SenderApprovalStatus | null = null;
  statusFilter: SenderStatus | null = null;
  page = 1;
  size = 20;

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.listSenderIds({
      search: this.search || undefined,
      approval_status: this.approvalFilter,
      status: this.statusFilter,
      page: this.page, size: this.size,
    }).subscribe({
      next: (res) => { this.rows.set(res.data); this.total.set(res.meta.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load sender IDs.'); },
    });
  }
  applyFilters(): void { this.page = 1; this.load(); }
  onPage(e: PageEvent): void { this.page = e.pageIndex + 1; this.size = e.pageSize; this.load(); }

  create(): void {
    this.dialog.open(SmsSenderCreateDialogComponent, { autoFocus: false })
      .afterClosed().subscribe((created) => { if (created) this.load(); });
  }
  edit(s: SmsSenderId): void {
    this.dialog.open(SmsSenderCreateDialogComponent, { autoFocus: false, data: { sender: s } })
      .afterClosed().subscribe((updated) => { if (updated) this.load(); });
  }
  setDefault(s: SmsSenderId): void {
    this.api.setDefaultSenderId(s.id).subscribe({ next: () => { this.notify.success(`${s.sender_id} is now the default.`); this.load(); }, error: () => this.notify.error('Unable to set default.') });
  }
  activate(s: SmsSenderId): void {
    this.api.activateSenderId(s.id).subscribe({ next: () => { this.notify.success('Sender activated.'); this.load(); }, error: () => this.notify.error('Unable to activate.') });
  }
  deactivate(s: SmsSenderId): void {
    this.api.deactivateSenderId(s.id).subscribe({ next: () => { this.notify.success('Sender deactivated.'); this.load(); }, error: () => this.notify.error('Unable to deactivate.') });
  }
}
