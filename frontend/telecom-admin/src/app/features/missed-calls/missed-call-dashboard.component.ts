import { Component, inject, OnInit, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { MissedCallService } from './missed-call.service';
import { MissedCallDashboardStats } from './missed-call.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-missed-call-dashboard',
  standalone: true,
  imports: [MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  template: `
    <header class="page-header">
      <div>
        <h1>Missed Calls</h1>
        <p>Overview of incoming calls that were not answered.</p>
      </div>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (stats(); as s) {
      <div class="stats-grid">
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon today"><mat-icon>today</mat-icon></div>
            <div class="stat-value">{{ s.missed_today }}</div>
            <div class="stat-label">Missed Today</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon pending"><mat-icon>pending_actions</mat-icon></div>
            <div class="stat-value">{{ s.pending_callbacks }}</div>
            <div class="stat-label">Pending Callbacks</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon success"><mat-icon>check_circle</mat-icon></div>
            <div class="stat-value">{{ s.callback_success_rate_pct }}%</div>
            <div class="stat-label">Callback Success Rate</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon time"><mat-icon>timer</mat-icon></div>
            <div class="stat-value">{{ formatTime(s.avg_callback_time_seconds) }}</div>
            <div class="stat-label">Avg Callback Time</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon total"><mat-icon>phone_missed</mat-icon></div>
            <div class="stat-value">{{ s.total_missed }}</div>
            <div class="stat-label">Total Missed</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon callbacks"><mat-icon>phone_callback</mat-icon></div>
            <div class="stat-value">{{ s.total_callbacks }}</div>
            <div class="stat-label">Total Callbacks</div>
          </mat-card-content>
        </mat-card>
      </div>

      <h2 class="section-heading">By Status</h2>
      <div class="status-grid">
        @for (entry of statusEntries(s); track entry.label) {
          <mat-card [class]="'status-card ' + entry.key">
            <mat-card-content>
              <span class="count">{{ entry.count }}</span>
              <span class="label">{{ entry.label }}</span>
            </mat-card-content>
          </mat-card>
        }
      </div>

      <div class="quick-links">
        <a mat-stroked-button routerLink="/missed-calls/list">View All Missed Calls</a>
      </div>
    }
  `,
  styles: [`
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .stat-card mat-card-content {
      display: flex; flex-direction: column; align-items: center;
      padding: 24px 16px; gap: 8px;
    }
    .stat-icon {
      width: 48px; height: 48px; border-radius: 12px;
      display: flex; align-items: center; justify-content: center; color: #fff;
    }
    .stat-icon.today { background: #e65100; }
    .stat-icon.pending { background: #f9a825; }
    .stat-icon.success { background: #388e3c; }
    .stat-icon.time { background: #0288d1; }
    .stat-icon.total { background: #d32f2f; }
    .stat-icon.callbacks { background: #7b1fa2; }
    .stat-value { font-size: 28px; font-weight: 700; }
    .stat-label { font-size: 13px; color: #666; }

    .section-heading { margin: 8px 0 16px; font-size: 18px; font-weight: 600; }
    .status-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 12px; margin-bottom: 32px;
    }
    .status-card mat-card-content {
      display: flex; align-items: center; gap: 10px; padding: 16px;
    }
    .status-card .count { font-size: 22px; font-weight: 700; }
    .status-card .label { font-size: 13px; color: #666; }
    .status-card.new { border-left: 4px solid #e65100; }
    .status-card.acknowledged { border-left: 4px solid #f9a825; }
    .status-card.returned { border-left: 4px solid #0288d1; }
    .status-card.closed { border-left: 4px solid #388e3c; }

    .quick-links { display: flex; gap: 12px; flex-wrap: wrap; }
  `],
})
export class MissedCallDashboardComponent implements OnInit {
  private readonly svc = inject(MissedCallService);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  stats = signal<MissedCallDashboardStats | null>(null);

  ngOnInit(): void {
    this.svc.getDashboardStats().subscribe({
      next: (d) => { this.stats.set(d); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Failed to load missed call stats'); },
    });
  }

  formatTime(secs: number): string {
    if (secs < 60) return `${Math.round(secs)}s`;
    const m = Math.floor(secs / 60);
    return `${m}m ${Math.round(secs % 60)}s`;
  }

  statusEntries(s: MissedCallDashboardStats): { key: string; label: string; count: number }[] {
    return [
      { key: 'new', label: 'New', count: s.by_status['new'] || 0 },
      { key: 'acknowledged', label: 'Acknowledged', count: s.by_status['acknowledged'] || 0 },
      { key: 'returned', label: 'Returned', count: s.by_status['returned'] || 0 },
      { key: 'closed', label: 'Closed', count: s.by_status['closed'] || 0 },
    ];
  }
}
