import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
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

import { VoiceService } from './voice.service';
import { VoiceCallLog, CallDirection, CallStatus } from './voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-call-history',
  standalone: true,
  imports: [
    DatePipe, FormsModule,
    MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatPaginatorModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Call History</h1>
        <p>Complete call detail records for your company.</p>
      </div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" placeholder="Phone number..." />
        <mat-icon matPrefix>search</mat-icon>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Direction</mat-label>
        <mat-select [(ngModel)]="direction">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="inbound">Inbound</mat-option>
          <mat-option value="outbound">Outbound</mat-option>
        </mat-select>
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
      <table mat-table [dataSource]="calls()" class="full-width">
        <ng-container matColumnDef="direction">
          <th mat-header-cell *matHeaderCellDef>Dir</th>
          <td mat-cell *matCellDef="let c">
            <mat-icon [matTooltip]="c.direction" class="dir-icon">
              {{ c.direction === 'outbound' ? 'call_made' : 'call_received' }}
            </mat-icon>
          </td>
        </ng-container>
        <ng-container matColumnDef="caller">
          <th mat-header-cell *matHeaderCellDef>Caller</th>
          <td mat-cell *matCellDef="let c">
            {{ c.caller_extension_number || c.caller_number }}
          </td>
        </ng-container>
        <ng-container matColumnDef="callee">
          <th mat-header-cell *matHeaderCellDef>Callee</th>
          <td mat-cell *matCellDef="let c">
            {{ c.callee_extension_number || c.callee_number }}
          </td>
        </ng-container>
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef>Status</th>
          <td mat-cell *matCellDef="let c">
            <mat-chip [class]="'cdr-status-' + c.status">{{ c.status }}</mat-chip>
          </td>
        </ng-container>
        <ng-container matColumnDef="started_at">
          <th mat-header-cell *matHeaderCellDef>Start Time</th>
          <td mat-cell *matCellDef="let c">{{ c.started_at | date:'short' }}</td>
        </ng-container>
        <ng-container matColumnDef="duration">
          <th mat-header-cell *matHeaderCellDef>Duration</th>
          <td mat-cell *matCellDef="let c">{{ formatSecs(c.duration_seconds) }}</td>
        </ng-container>
        <ng-container matColumnDef="hangup_cause">
          <th mat-header-cell *matHeaderCellDef>Hangup Cause</th>
          <td mat-cell *matCellDef="let c">{{ c.hangup_cause || '—' }}</td>
        </ng-container>
        <ng-container matColumnDef="initiator">
          <th mat-header-cell *matHeaderCellDef>Initiated By</th>
          <td mat-cell *matCellDef="let c">{{ c.initiator_name || '—' }}</td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns;"></tr>
      </table>

      @if (!loading() && calls().length === 0) {
        <div class="empty-state">
          <mat-icon>history</mat-icon>
          <p>No call records match your filters.</p>
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
      display: flex;
      gap: 12px;
      flex-wrap: wrap;
      align-items: center;
      margin-bottom: 16px;
    }
    .filters mat-form-field { width: 160px; }
    .full-width { width: 100%; }
    .empty-state { text-align: center; padding: 48px 0; color: #888; }
    .empty-state mat-icon { font-size: 48px; height: 48px; width: 48px; }
    .dir-icon { font-size: 20px; }
    .cdr-status-completed { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .cdr-status-answered { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .cdr-status-failed { background: #ffebee !important; color: #c62828 !important; }
    .cdr-status-busy { background: #fff3e0 !important; color: #e65100 !important; }
    .cdr-status-no_answer { background: #fce4ec !important; color: #880e4f !important; }
    .cdr-status-cancelled { background: #f3e5f5 !important; color: #6a1b9a !important; }
    .cdr-status-initiated { background: #e3f2fd !important; color: #1565c0 !important; }
    .cdr-status-ringing { background: #e3f2fd !important; color: #1565c0 !important; }
  `],
})
export class VoiceCallHistoryComponent implements OnInit {
  private readonly svc = inject(VoiceService);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  calls = signal<VoiceCallLog[]>([]);
  total = signal(0);
  pageIndex = signal(0);
  pageSize = 20;

  // Filters
  search = '';
  direction: CallDirection | null = null;
  statusFilter: CallStatus | null = null;
  fromDate: string | null = null;
  toDate: string | null = null;

  statuses: CallStatus[] = [
    'initiated', 'ringing', 'answered', 'busy',
    'no_answer', 'failed', 'cancelled', 'completed',
  ];

  columns = [
    'direction', 'caller', 'callee', 'status',
    'started_at', 'duration', 'hangup_cause', 'initiator',
  ];

  ngOnInit(): void { this.load(); }

  apply(): void {
    this.pageIndex.set(0);
    this.load();
  }

  reset(): void {
    this.search = '';
    this.direction = null;
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

  private load(): void {
    this.loading.set(true);
    this.svc.listCalls({
      offset: this.pageIndex() * this.pageSize,
      limit: this.pageSize,
      direction: this.direction,
      status: this.statusFilter,
      search: this.search || null,
      from_date: this.fromDate ? `${this.fromDate}T00:00:00Z` : null,
      to_date: this.toDate ? `${this.toDate}T23:59:59Z` : null,
    }).subscribe({
      next: (d) => {
        this.calls.set(d.items);
        this.total.set(d.total);
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.notify.error('Failed to load call history'); },
    });
  }

  formatSecs(s: number | null): string {
    if (s == null) return '—';
    const m = Math.floor(s / 60);
    const sec = s % 60;
    return `${m}:${sec.toString().padStart(2, '0')}`;
  }
}
