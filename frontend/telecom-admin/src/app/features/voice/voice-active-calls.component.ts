import { Component, inject, OnDestroy, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { VoiceService } from './voice.service';
import { VoiceCallLog } from './voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-active-calls',
  standalone: true,
  imports: [
    DatePipe,
    MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatChipsModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Active Calls</h1>
        <p>Calls currently in progress. Auto-refreshes every 5 seconds.</p>
      </div>
      <button mat-stroked-button (click)="load()">
        <mat-icon>refresh</mat-icon> Refresh
      </button>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    <mat-card>
      <table mat-table [dataSource]="calls()" class="full-width">
        <ng-container matColumnDef="direction">
          <th mat-header-cell *matHeaderCellDef>Dir</th>
          <td mat-cell *matCellDef="let c">
            <mat-icon [matTooltip]="c.direction">
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
            <mat-chip [class]="'call-status-' + c.status">{{ c.status }}</mat-chip>
          </td>
        </ng-container>
        <ng-container matColumnDef="started_at">
          <th mat-header-cell *matHeaderCellDef>Started</th>
          <td mat-cell *matCellDef="let c">{{ c.started_at | date:'shortTime' }}</td>
        </ng-container>
        <ng-container matColumnDef="elapsed">
          <th mat-header-cell *matHeaderCellDef>Elapsed</th>
          <td mat-cell *matCellDef="let c">{{ elapsed(c) }}</td>
        </ng-container>
        <ng-container matColumnDef="initiator">
          <th mat-header-cell *matHeaderCellDef>Initiated By</th>
          <td mat-cell *matCellDef="let c">{{ c.initiator_name || '—' }}</td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let c">
            <button mat-icon-button color="warn" matTooltip="Hang up"
              (click)="hangup(c)">
              <mat-icon>call_end</mat-icon>
            </button>
            @if (c.status === 'initiated') {
              <button mat-icon-button color="primary" matTooltip="Simulate answer"
                (click)="simulateAnswer(c)">
                <mat-icon>phone_forwarded</mat-icon>
              </button>
            }
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns;"></tr>
      </table>

      @if (!loading() && calls().length === 0) {
        <div class="empty-state">
          <mat-icon>phone_paused</mat-icon>
          <p>No active calls right now.</p>
        </div>
      }
    </mat-card>
  `,
  styles: [`
    .full-width { width: 100%; }
    .empty-state { text-align: center; padding: 48px 0; color: #888; }
    .empty-state mat-icon { font-size: 48px; height: 48px; width: 48px; }
    .call-status-initiated { background: #fff3e0 !important; color: #e65100 !important; }
    .call-status-ringing { background: #e3f2fd !important; color: #1565c0 !important; }
    .call-status-answered { background: #e8f5e9 !important; color: #2e7d32 !important; }
  `],
})
export class VoiceActiveCallsComponent implements OnInit, OnDestroy {
  private readonly svc = inject(VoiceService);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  calls = signal<VoiceCallLog[]>([]);

  columns = [
    'direction', 'caller', 'callee', 'status',
    'started_at', 'elapsed', 'initiator', 'actions',
  ];

  private intervalId: ReturnType<typeof setInterval> | null = null;

  ngOnInit(): void {
    this.load();
    this.intervalId = setInterval(() => this.load(), 5000);
  }

  ngOnDestroy(): void {
    if (this.intervalId) clearInterval(this.intervalId);
  }

  load(): void {
    this.loading.set(true);
    this.svc.getActiveCalls().subscribe({
      next: (d) => { this.calls.set(d); this.loading.set(false); },
      error: () => { this.loading.set(false); },
    });
  }

  elapsed(c: VoiceCallLog): string {
    const start = new Date(c.answered_at || c.started_at).getTime();
    const secs = Math.floor((Date.now() - start) / 1000);
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m}:${s.toString().padStart(2, '0')}`;
  }

  hangup(c: VoiceCallLog): void {
    this.svc.hangupCall(c.id).subscribe({
      next: () => { this.load(); this.notify.success('Call ended'); },
      error: (e) => this.notify.error(e?.error?.detail || 'Hangup failed'),
    });
  }

  simulateAnswer(c: VoiceCallLog): void {
    this.svc.updateCallStatus(c.id, 'answered').subscribe({
      next: () => this.load(),
      error: (e) => this.notify.error(e?.error?.detail || 'Status update failed'),
    });
  }
}
