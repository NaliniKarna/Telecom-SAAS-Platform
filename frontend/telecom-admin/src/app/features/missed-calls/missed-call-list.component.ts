import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatMenuModule } from '@angular/material/menu';

import { MissedCallService } from './missed-call.service';
import { MissedCallRead, MissedCallStatus } from './missed-call.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-missed-call-list',
  standalone: true,
  imports: [
    DatePipe, FormsModule, RouterLink,
    MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatPaginatorModule, MatProgressBarModule, MatTooltipModule, MatMenuModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Missed Calls</h1>
        <p>All inbound calls that were not answered.</p>
      </div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" placeholder="Phone number or name..." />
        <mat-icon matPrefix>search</mat-icon>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter">
          <mat-option [value]="null">All</mat-option>
          @for (s of statuses; track s) {
            <mat-option [value]="s">{{ s }}</mat-option>
          }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>From</mat-label>
        <input matInput type="date" [(ngModel)]="fromDate" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>To</mat-label>
        <input matInput type="date" [(ngModel)]="toDate" />
      </mat-form-field>
      <button mat-flat-button color="primary" (click)="apply()">
        <mat-icon>filter_alt</mat-icon> Apply
      </button>
      <button mat-stroked-button (click)="reset()">Reset</button>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    <mat-card>
      <table mat-table [dataSource]="items()" class="full-width">
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef>Status</th>
          <td mat-cell *matCellDef="let m">
            <mat-chip [class]="'mc-status-' + m.status">{{ m.status }}</mat-chip>
          </td>
        </ng-container>
        <ng-container matColumnDef="caller">
          <th mat-header-cell *matHeaderCellDef>Caller</th>
          <td mat-cell *matCellDef="let m">
            <div>{{ m.caller_number }}</div>
            @if (m.caller_name) {
              <div class="sub-text">{{ m.caller_name }}</div>
            }
          </td>
        </ng-container>
        <ng-container matColumnDef="called">
          <th mat-header-cell *matHeaderCellDef>Called</th>
          <td mat-cell *matCellDef="let m">
            {{ m.called_extension_number || m.called_number }}
          </td>
        </ng-container>
        <ng-container matColumnDef="received_at">
          <th mat-header-cell *matHeaderCellDef>Received</th>
          <td mat-cell *matCellDef="let m">{{ m.received_at | date:'short' }}</td>
        </ng-container>
        <ng-container matColumnDef="ring_duration">
          <th mat-header-cell *matHeaderCellDef>Ring</th>
          <td mat-cell *matCellDef="let m">
            {{ m.ring_duration_seconds != null ? m.ring_duration_seconds + 's' : '—' }}
          </td>
        </ng-container>
        <ng-container matColumnDef="assignee">
          <th mat-header-cell *matHeaderCellDef>Assigned To</th>
          <td mat-cell *matCellDef="let m">{{ m.assignee_name || '—' }}</td>
        </ng-container>
        <ng-container matColumnDef="callbacks">
          <th mat-header-cell *matHeaderCellDef>Callbacks</th>
          <td mat-cell *matCellDef="let m">{{ m.callback_count }}</td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let m">
            <a mat-icon-button [routerLink]="['/missed-calls', m.id]" matTooltip="View detail">
              <mat-icon>visibility</mat-icon>
            </a>
            <button mat-icon-button [matMenuTriggerFor]="actMenu" matTooltip="Actions">
              <mat-icon>more_vert</mat-icon>
            </button>
            <mat-menu #actMenu="matMenu">
              @if (m.status === 'new') {
                <button mat-menu-item (click)="setStatus(m, 'acknowledged')">
                  <mat-icon>visibility</mat-icon> Acknowledge
                </button>
              }
              @if (m.status !== 'closed') {
                <button mat-menu-item (click)="setStatus(m, 'closed')">
                  <mat-icon>check_circle</mat-icon> Close
                </button>
              }
            </mat-menu>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns;"
          [class.row-new]="row.status === 'new'"></tr>
      </table>

      @if (!loading() && items().length === 0) {
        <div class="empty-state">
          <mat-icon>phone_missed</mat-icon>
          <p>No missed calls match your filters.</p>
        </div>
      }

      <mat-paginator
        [length]="total()"
        [pageSize]="pageSize"
        [pageSizeOptions]="[10, 20, 50]"
        [pageIndex]="pageIndex()"
        (page)="onPage($event)"
        showFirstLastButtons>
      </mat-paginator>
    </mat-card>
  `,
  styles: [`
    .filters {
      display: flex; gap: 12px; flex-wrap: wrap;
      align-items: center; margin-bottom: 16px;
    }
    .filters mat-form-field { width: 160px; }
    .full-width { width: 100%; }
    .empty-state { text-align: center; padding: 48px 0; color: #888; }
    .empty-state mat-icon { font-size: 48px; height: 48px; width: 48px; }
    .sub-text { font-size: 12px; color: #888; }
    .row-new { background: #fff8e1; }
    .mc-status-new { background: #fff3e0 !important; color: #e65100 !important; }
    .mc-status-acknowledged { background: #fff9c4 !important; color: #f57f17 !important; }
    .mc-status-returned { background: #e3f2fd !important; color: #1565c0 !important; }
    .mc-status-closed { background: #e8f5e9 !important; color: #2e7d32 !important; }
  `],
})
export class MissedCallListComponent implements OnInit {
  private readonly svc = inject(MissedCallService);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  items = signal<MissedCallRead[]>([]);
  total = signal(0);
  pageIndex = signal(0);
  pageSize = 20;

  search = '';
  statusFilter: MissedCallStatus | null = null;
  fromDate: string | null = null;
  toDate: string | null = null;

  statuses: MissedCallStatus[] = ['new', 'acknowledged', 'returned', 'closed'];
  columns = [
    'status', 'caller', 'called', 'received_at',
    'ring_duration', 'assignee', 'callbacks', 'actions',
  ];

  ngOnInit(): void { this.load(); }

  apply(): void { this.pageIndex.set(0); this.load(); }

  reset(): void {
    this.search = '';
    this.statusFilter = null;
    this.fromDate = null;
    this.toDate = null;
    this.pageIndex.set(0);
    this.load();
  }

  onPage(e: PageEvent): void {
    this.pageIndex.set(e.pageIndex);
    this.pageSize = e.pageSize;
    this.load();
  }

  setStatus(m: MissedCallRead, status: string): void {
    this.svc.updateStatus(m.id, status).subscribe({
      next: () => { this.load(); this.notify.success(`Status updated to ${status}`); },
      error: () => this.notify.error('Status update failed'),
    });
  }

  private load(): void {
    this.loading.set(true);
    this.svc.list({
      offset: this.pageIndex() * this.pageSize,
      limit: this.pageSize,
      status: this.statusFilter,
      search: this.search || null,
      from_date: this.fromDate ? `${this.fromDate}T00:00:00Z` : null,
      to_date: this.toDate ? `${this.toDate}T23:59:59Z` : null,
    }).subscribe({
      next: (d) => { this.items.set(d.items); this.total.set(d.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Failed to load missed calls'); },
    });
  }
}
