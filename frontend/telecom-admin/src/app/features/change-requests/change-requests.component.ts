import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTabsModule } from '@angular/material/tabs';
import { MatDialog } from '@angular/material/dialog';

import { ChangeRequestService } from './change-request.service';
import { ChangeRequest, RecentActivity } from './change-request.models';
import { NotificationService } from '../../core/services/notification.service';
import { RejectReasonDialogComponent } from './reject-reason-dialog.component';

const FIELD_LABELS: Record<string, string> = {
  name: 'Company name',
  contact_email: 'Contact email',
  contact_phone: 'Contact phone',
  address: 'Address',
  timezone: 'Timezone',
  logo_url: 'Logo',
};

@Component({
  selector: 'app-change-requests',
  standalone: true,
  imports: [
    DatePipe, MatCardModule, MatButtonModule, MatIconModule,
    MatProgressBarModule, MatTabsModule,
  ],
  template: `
    <header class="page-header">
      <h1>Change Requests</h1>
      <p>Review company-settings changes that require approval.</p>
    </header>

    <mat-tab-group>
      <!-- Pending approvals -->
      <mat-tab label="Pending Approval">
        @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
        @if (error()) {
          <mat-card appearance="outlined" class="state-card">
            <mat-card-content>
              <mat-icon>error_outline</mat-icon>
              <p>Couldn't load change requests.</p>
              <button mat-stroked-button (click)="load()">Retry</button>
            </mat-card-content>
          </mat-card>
        }
        @if (!loading() && pending().length === 0) {
          <div class="empty">
            <mat-icon>task_alt</mat-icon>
            <p>No pending requests. You're all caught up.</p>
          </div>
        }
        @for (req of pending(); track req.id) {
          <mat-card appearance="outlined" class="req">
            <mat-card-header>
              <mat-card-title>{{ req.company_name ?? 'Company' }}</mat-card-title>
              <mat-card-subtitle>
                Requested by {{ req.requester_name ?? 'a company admin' }}
                · {{ req.created_at | date: 'medium' }}
              </mat-card-subtitle>
            </mat-card-header>
            <mat-card-content>
              <table class="diff">
                <thead><tr><th>Field</th><th>Current</th><th></th><th>Requested</th></tr></thead>
                <tbody>
                  @for (f of fields(req); track f) {
                    <tr>
                      <td class="diff__field">{{ label(f) }}</td>
                      <td class="diff__old">{{ req.changes[f].old ?? '—' }}</td>
                      <td class="diff__arrow"><mat-icon>arrow_forward</mat-icon></td>
                      <td class="diff__new">{{ req.changes[f].new ?? '—' }}</td>
                    </tr>
                  }
                </tbody>
              </table>
            </mat-card-content>
            <mat-card-actions align="end">
              <button mat-button color="warn" (click)="reject(req)" [disabled]="busy() === req.id">Reject</button>
              <button mat-flat-button color="primary" (click)="approve(req)" [disabled]="busy() === req.id">Approve</button>
            </mat-card-actions>
          </mat-card>
        }
      </mat-tab>

      <!-- Recent activity (immediate-save changes) -->
      <mat-tab label="Recent Activity">
        @if (activityLoading()) { <mat-progress-bar mode="indeterminate" /> }
        @if (!activityLoading() && activity().length === 0) {
          <div class="empty"><mat-icon>history</mat-icon><p>No recent settings activity.</p></div>
        }
        @if (activity().length > 0) {
          <mat-card appearance="outlined">
            <mat-card-content>
              <p class="hint">Settings changes that applied immediately (no approval required).</p>
              <ul class="list">
                @for (a of activity(); track a.id) {
                  <li>
                    <span class="list__company">{{ a.company_name ?? 'Company' }}</span>
                    <span class="muted">changed {{ a.changed_fields.length ? humanFields(a.changed_fields) : a.action }}</span>
                    <span class="muted date">{{ a.created_at | date: 'short' }}</span>
                  </li>
                }
              </ul>
            </mat-card-content>
          </mat-card>
        }
      </mat-tab>
    </mat-tab-group>
  `,
  styles: [
    `
      .page-header { margin-bottom: 1rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .req { margin: 1rem 0; }
      .diff { width: 100%; border-collapse: collapse; }
      .diff th { text-align: left; font: var(--mat-sys-label-small); color: var(--mat-sys-on-surface-variant); padding-bottom: 0.5rem; }
      .diff td { padding: 0.35rem 0.5rem 0.35rem 0; vertical-align: middle; }
      .diff__field { font-weight: 500; }
      .diff__old { color: var(--mat-sys-on-surface-variant); text-decoration: line-through; }
      .diff__new { color: var(--mat-sys-primary); font-weight: 500; }
      .diff__arrow mat-icon { font-size: 1.1rem; width: 1.1rem; height: 1.1rem; opacity: 0.5; }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 3rem 1rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
      .hint { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); margin: 0 0 0.75rem; }
      .list { list-style: none; margin: 0; padding: 0; }
      .list li { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
      .list li:last-child { border-bottom: none; }
      .list__company { font-weight: 500; }
      .muted { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .date { margin-left: auto; }
      .state-card mat-card-content { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2rem; }
    `,
  ],
})
export class ChangeRequestsComponent {
  private readonly api = inject(ChangeRequestService);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly pending = signal<ChangeRequest[]>([]);
  readonly activity = signal<RecentActivity[]>([]);
  readonly loading = signal(false);
  readonly activityLoading = signal(false);
  readonly error = signal(false);
  readonly busy = signal<string | null>(null);

  constructor() {
    this.load();
    this.loadActivity();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(false);
    this.api.listPending().subscribe({
      next: (r) => { this.pending.set(r); this.loading.set(false); },
      error: () => { this.error.set(true); this.loading.set(false); },
    });
  }

  loadActivity(): void {
    this.activityLoading.set(true);
    this.api.recentActivity().subscribe({
      next: (a) => { this.activity.set(a); this.activityLoading.set(false); },
      error: () => this.activityLoading.set(false),
    });
  }

  fields(req: ChangeRequest): string[] {
    return Object.keys(req.changes);
  }
  label(f: string): string {
    return FIELD_LABELS[f] ?? f;
  }
  humanFields(fields: string[]): string {
    return fields.map((f) => this.label(f).toLowerCase()).join(', ');
  }

  approve(req: ChangeRequest): void {
    this.busy.set(req.id);
    this.api.approve(req.id).subscribe({
      next: () => {
        this.notify.success(`Approved changes for ${req.company_name ?? 'company'}.`);
        this.pending.update((list) => list.filter((r) => r.id !== req.id));
        this.busy.set(null);
        this.loadActivity();
      },
      error: () => this.busy.set(null),
    });
  }

  reject(req: ChangeRequest): void {
    const ref = this.dialog.open(RejectReasonDialogComponent, { autoFocus: false });
    ref.afterClosed().subscribe((result) => {
      if (result === undefined || result === false) return; // cancelled
      this.busy.set(req.id);
      this.api.reject(req.id, result || null).subscribe({
        next: () => {
          this.notify.success(`Rejected changes for ${req.company_name ?? 'company'}.`);
          this.pending.update((list) => list.filter((r) => r.id !== req.id));
          this.busy.set(null);
        },
        error: () => this.busy.set(null),
      });
    });
  }
}
