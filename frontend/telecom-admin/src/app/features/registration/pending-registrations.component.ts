import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog } from '@angular/material/dialog';

import { RegistrationService } from './registration.service';
import { PendingRegistration } from './registration.models';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-pending-registrations',
  standalone: true,
  imports: [
    DatePipe, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatTooltipModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Pending Registrations</h1>
        <p>Companies waiting for approval before their admin can sign in.</p>
      </div>
      <button mat-stroked-button (click)="load()" [disabled]="loading()">
        <mat-icon>refresh</mat-icon> Refresh
      </button>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>inbox</mat-icon><p>No pending registrations.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="company">
            <th mat-header-cell *matHeaderCellDef>Company</th>
            <td mat-cell *matCellDef="let r">
              <strong>{{ r.company_name }}</strong>
              <div class="sub">{{ r.slug }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="admin">
            <th mat-header-cell *matHeaderCellDef>Admin</th>
            <td mat-cell *matCellDef="let r">
              {{ r.admin_name || '—' }}
              <div class="sub">{{ r.admin_email }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="verified">
            <th mat-header-cell *matHeaderCellDef>Email verified</th>
            <td mat-cell *matCellDef="let r">
              @if (r.admin_email_verified) {
                <span class="chip chip--yes"><mat-icon inline>check_circle</mat-icon> Verified</span>
              } @else {
                <span class="chip chip--no"><mat-icon inline>schedule</mat-icon> Not yet</span>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="submitted">
            <th mat-header-cell *matHeaderCellDef>Submitted</th>
            <td mat-cell *matCellDef="let r">{{ r.submitted_at | date: 'medium' }}</td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let r">
              <button
                mat-flat-button color="primary"
                [disabled]="!r.admin_email_verified || busyId() === r.company_id"
                [matTooltip]="r.admin_email_verified ? '' : 'Admin must verify their email before approval'"
                (click)="approve(r)"
              >
                <mat-icon>check</mat-icon> Approve
              </button>
              <button
                mat-stroked-button color="warn"
                [disabled]="busyId() === r.company_id"
                (click)="reject(r)"
              >
                <mat-icon>close</mat-icon> Reject
              </button>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
      </mat-card>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; gap: 1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); }
    table { width: 100%; }
    .sub { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    td.mat-column-actions, th.mat-column-actions { display: flex; gap: .5rem; align-items: center; }
    .chip { display: inline-flex; align-items: center; gap: .25rem; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; }
    .chip mat-icon { font-size: 1rem; height: 1rem; width: 1rem; }
    .chip--yes { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--no { background: var(--mat-sys-surface-container-highest); color: var(--mat-sys-on-surface-variant); }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class PendingRegistrationsComponent {
  private readonly api = inject(RegistrationService);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly cols = ['company', 'admin', 'verified', 'submitted', 'actions'];
  readonly rows = signal<PendingRegistration[]>([]);
  readonly loading = signal(false);
  readonly busyId = signal<string | null>(null);

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.listPending().subscribe({
      next: (rows) => { this.rows.set(rows); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load pending registrations.'); },
    });
  }

  approve(r: PendingRegistration): void {
    this.busyId.set(r.company_id);
    this.api.approve(r.company_id).subscribe({
      next: () => {
        this.notify.success(`${r.company_name} approved — admin can now sign in.`);
        this.busyId.set(null);
        this.load();
      },
      error: () => { this.busyId.set(null); this.notify.error('Unable to approve this registration.'); },
    });
  }

  reject(r: PendingRegistration): void {
    const data: ConfirmDialogData = {
      title: 'Reject registration',
      message: `Reject "${r.company_name}"? The admin will not be able to sign in.`,
      confirmText: 'Reject', destructive: true,
    };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.busyId.set(r.company_id);
      this.api.reject(r.company_id).subscribe({
        next: () => {
          this.notify.success(`${r.company_name} rejected.`);
          this.busyId.set(null);
          this.load();
        },
        error: () => { this.busyId.set(null); this.notify.error('Unable to reject this registration.'); },
      });
    });
  }
}
