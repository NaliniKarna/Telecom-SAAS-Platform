import { Component, inject, OnInit, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { RouterLink } from '@angular/router';

import { VoiceService } from './voice.service';
import { ExtensionStatusSummary, VoiceOverviewStats } from './voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-dashboard',
  standalone: true,
  imports: [MatCardModule, MatIconModule, MatProgressBarModule, RouterLink],
  template: `
    <header class="page-header">
      <div>
        <h1>Voice Dashboard</h1>
        <p>Overview of your voice activity and extension status.</p>
      </div>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (overview(); as o) {
      <div class="stats-grid">
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon total"><mat-icon>call</mat-icon></div>
            <div class="stat-value">{{ o.total_calls }}</div>
            <div class="stat-label">Total Calls</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon answered"><mat-icon>call_received</mat-icon></div>
            <div class="stat-value">{{ o.answered_calls }}</div>
            <div class="stat-label">Answered</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon rate"><mat-icon>percent</mat-icon></div>
            <div class="stat-value">{{ o.answer_rate_pct }}%</div>
            <div class="stat-label">Answer Rate</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon active"><mat-icon>phone_in_talk</mat-icon></div>
            <div class="stat-value">{{ o.active_calls }}</div>
            <div class="stat-label">Active Now</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon duration"><mat-icon>timer</mat-icon></div>
            <div class="stat-value">{{ formatDuration(o.avg_duration_seconds) }}</div>
            <div class="stat-label">Avg Duration</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon outbound"><mat-icon>call_made</mat-icon></div>
            <div class="stat-value">{{ o.outbound_calls }}</div>
            <div class="stat-label">Outbound</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon inbound"><mat-icon>call_received</mat-icon></div>
            <div class="stat-value">{{ o.inbound_calls }}</div>
            <div class="stat-label">Inbound</div>
          </mat-card-content>
        </mat-card>
        <mat-card class="stat-card">
          <mat-card-content>
            <div class="stat-icon failed"><mat-icon>call_missed</mat-icon></div>
            <div class="stat-value">{{ o.failed_calls }}</div>
            <div class="stat-label">Failed</div>
          </mat-card-content>
        </mat-card>
      </div>
    }

    @if (extStatus(); as s) {
      <h2 class="section-heading">Extension Status</h2>
      <div class="ext-status-grid">
        <mat-card class="ext-status-card available">
          <mat-card-content>
            <mat-icon>circle</mat-icon>
            <span class="count">{{ s.available }}</span>
            <span class="label">Available</span>
          </mat-card-content>
        </mat-card>
        <mat-card class="ext-status-card busy">
          <mat-card-content>
            <mat-icon>circle</mat-icon>
            <span class="count">{{ s.busy }}</span>
            <span class="label">Busy</span>
          </mat-card-content>
        </mat-card>
        <mat-card class="ext-status-card away">
          <mat-card-content>
            <mat-icon>circle</mat-icon>
            <span class="count">{{ s.away }}</span>
            <span class="label">Away</span>
          </mat-card-content>
        </mat-card>
        <mat-card class="ext-status-card offline">
          <mat-card-content>
            <mat-icon>circle</mat-icon>
            <span class="count">{{ s.offline }}</span>
            <span class="label">Offline</span>
          </mat-card-content>
        </mat-card>
      </div>
    }

    <div class="quick-links">
      <a mat-stroked-button routerLink="/voice/extensions">Manage Extensions</a>
      <a mat-stroked-button routerLink="/voice/dialer">Open Dialer</a>
      <a mat-stroked-button routerLink="/voice/active">Active Calls</a>
      <a mat-stroked-button routerLink="/voice/calls">Call History</a>
    </div>
  `,
  styles: [`
    .stats-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 16px;
      margin-bottom: 32px;
    }
    .stat-card mat-card-content {
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 24px 16px;
      gap: 8px;
    }
    .stat-icon {
      width: 48px;
      height: 48px;
      border-radius: 12px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
    }
    .stat-icon.total { background: #1976d2; }
    .stat-icon.answered { background: #388e3c; }
    .stat-icon.rate { background: #7b1fa2; }
    .stat-icon.active { background: #00897b; }
    .stat-icon.duration { background: #f57c00; }
    .stat-icon.outbound { background: #0288d1; }
    .stat-icon.inbound { background: #5c6bc0; }
    .stat-icon.failed { background: #d32f2f; }
    .stat-value { font-size: 28px; font-weight: 700; }
    .stat-label { font-size: 13px; color: #666; }

    .section-heading { margin: 8px 0 16px; font-size: 18px; font-weight: 600; }

    .ext-status-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 32px;
    }
    .ext-status-card mat-card-content {
      display: flex;
      align-items: center;
      gap: 10px;
      padding: 16px;
    }
    .ext-status-card .count { font-size: 24px; font-weight: 700; }
    .ext-status-card .label { font-size: 13px; color: #666; }
    .ext-status-card.available mat-icon { color: #388e3c; }
    .ext-status-card.busy mat-icon { color: #d32f2f; }
    .ext-status-card.away mat-icon { color: #f9a825; }
    .ext-status-card.offline mat-icon { color: #9e9e9e; }

    .quick-links { display: flex; gap: 12px; flex-wrap: wrap; }
  `],
})
export class VoiceDashboardComponent implements OnInit {
  private readonly svc = inject(VoiceService);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  overview = signal<VoiceOverviewStats | null>(null);
  extStatus = signal<ExtensionStatusSummary | null>(null);

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.svc.getOverview().subscribe({
      next: (d) => this.overview.set(d),
      error: () => this.notify.error('Failed to load voice overview'),
    });
    this.svc.getExtensionStatusSummary().subscribe({
      next: (d) => { this.extStatus.set(d); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Failed to load extension status'); },
    });
  }

  formatDuration(s: number): string {
    if (s < 60) return `${Math.round(s)}s`;
    const m = Math.floor(s / 60);
    const sec = Math.round(s % 60);
    return `${m}m ${sec}s`;
  }
}
