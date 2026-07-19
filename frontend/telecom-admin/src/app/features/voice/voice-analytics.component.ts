import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { VoiceService } from './voice.service';
import { TimeseriesPoint, VoiceOverviewStats } from './voice.models';
import { NotificationService } from '../../core/services/notification.service';

interface Bar {
  date: string;
  total: number;
  answered: number;
  failed: number;
  ah: number;  // answered bar height
  fh: number;  // failed bar height
}

@Component({
  selector: 'app-voice-analytics',
  standalone: true,
  imports: [
    FormsModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Voice Analytics</h1>
        <p>Call volume and performance over time.</p>
      </div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Period</mat-label>
        <mat-select [(ngModel)]="days">
          <mat-option [value]="7">Last 7 days</mat-option>
          <mat-option [value]="14">Last 14 days</mat-option>
          <mat-option [value]="30">Last 30 days</mat-option>
          <mat-option [value]="90">Last 90 days</mat-option>
        </mat-select>
      </mat-form-field>
      <button mat-flat-button color="primary" (click)="load()">
        <mat-icon>refresh</mat-icon> Refresh
      </button>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (overview(); as o) {
      <div class="overview-strip">
        <mat-card>
          <mat-card-content>
            <div class="ov-val">{{ o.total_calls }}</div>
            <div class="ov-lbl">Total Calls</div>
          </mat-card-content>
        </mat-card>
        <mat-card>
          <mat-card-content>
            <div class="ov-val">{{ o.answered_calls }}</div>
            <div class="ov-lbl">Answered</div>
          </mat-card-content>
        </mat-card>
        <mat-card>
          <mat-card-content>
            <div class="ov-val">{{ o.answer_rate_pct }}%</div>
            <div class="ov-lbl">Answer Rate</div>
          </mat-card-content>
        </mat-card>
        <mat-card>
          <mat-card-content>
            <div class="ov-val">{{ formatDuration(o.avg_duration_seconds) }}</div>
            <div class="ov-lbl">Avg Duration</div>
          </mat-card-content>
        </mat-card>
        <mat-card>
          <mat-card-content>
            <div class="ov-val">{{ o.failed_calls }}</div>
            <div class="ov-lbl">Failed</div>
          </mat-card-content>
        </mat-card>
      </div>
    }

    @if (bars().length) {
      <mat-card class="chart-card">
        <mat-card-header><mat-card-title>Daily Call Volume</mat-card-title></mat-card-header>
        <mat-card-content>
          <div class="chart-wrap">
            <svg [attr.viewBox]="'0 0 ' + chartW + ' ' + chartH" preserveAspectRatio="xMinYMid meet" class="chart-svg">
              @for (b of bars(); track b.date; let i = $index) {
                <!-- Answered bar -->
                <rect
                  [attr.x]="i * barStep + barPad"
                  [attr.y]="chartH - 24 - b.ah"
                  [attr.width]="barW"
                  [attr.height]="b.ah"
                  fill="#66bb6a"
                  rx="2">
                  <title>{{ b.date }}: {{ b.answered }} answered</title>
                </rect>
                <!-- Failed bar (stacked on top) -->
                <rect
                  [attr.x]="i * barStep + barPad"
                  [attr.y]="chartH - 24 - b.ah - b.fh"
                  [attr.width]="barW"
                  [attr.height]="b.fh"
                  fill="#ef5350"
                  rx="2">
                  <title>{{ b.date }}: {{ b.failed }} failed</title>
                </rect>
                <!-- Date label -->
                @if (i % labelStep() === 0) {
                  <text
                    [attr.x]="i * barStep + barPad + barW / 2"
                    [attr.y]="chartH - 4"
                    text-anchor="middle"
                    class="date-label">
                    {{ shortDate(b.date) }}
                  </text>
                }
              }
            </svg>
          </div>
          <div class="legend">
            <span class="legend-item"><span class="swatch answered"></span> Answered</span>
            <span class="legend-item"><span class="swatch failed"></span> Failed</span>
          </div>
        </mat-card-content>
      </mat-card>
    }
  `,
  styles: [`
    .filters { display: flex; gap: 12px; align-items: center; margin-bottom: 16px; }
    .overview-strip {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }
    .ov-val { font-size: 24px; font-weight: 700; text-align: center; }
    .ov-lbl { font-size: 12px; color: #888; text-align: center; margin-top: 4px; }
    .chart-card { margin-bottom: 24px; }
    .chart-wrap { overflow-x: auto; }
    .chart-svg { width: 100%; height: 260px; }
    .date-label { font-size: 10px; fill: #999; }
    .legend { display: flex; gap: 16px; padding-top: 8px; }
    .legend-item { display: flex; align-items: center; gap: 4px; font-size: 13px; }
    .swatch { display: inline-block; width: 14px; height: 14px; border-radius: 3px; }
    .swatch.answered { background: #66bb6a; }
    .swatch.failed { background: #ef5350; }
  `],
})
export class VoiceAnalyticsComponent implements OnInit {
  private readonly svc = inject(VoiceService);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  days = 30;
  overview = signal<VoiceOverviewStats | null>(null);
  rawPoints = signal<TimeseriesPoint[]>([]);

  // Chart geometry
  chartH = 260;
  barW = 16;
  barPad = 4;
  get barStep() { return this.barW + this.barPad * 2; }
  get chartW() { return Math.max(this.rawPoints().length * this.barStep + 20, 200); }

  labelStep = computed(() => {
    const n = this.rawPoints().length;
    if (n <= 15) return 1;
    if (n <= 40) return 2;
    return 4;
  });

  bars = computed<Bar[]>(() => {
    const pts = this.rawPoints();
    const maxVal = Math.max(1, ...pts.map(p => p.total));
    const scale = (this.chartH - 40) / maxVal;
    return pts.map(p => ({
      date: p.date,
      total: p.total,
      answered: p.answered,
      failed: p.failed,
      ah: Math.max(1, p.answered * scale),
      fh: Math.max(p.failed > 0 ? 1 : 0, p.failed * scale),
    }));
  });

  ngOnInit(): void { this.load(); }

  load(): void {
    this.loading.set(true);
    this.svc.getOverview().subscribe({
      next: (d) => this.overview.set(d),
      error: () => this.notify.error('Failed to load overview'),
    });
    this.svc.getTimeseries(this.days).subscribe({
      next: (d) => { this.rawPoints.set(d.points); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Failed to load timeseries'); },
    });
  }

  shortDate(iso: string): string {
    const d = new Date(iso);
    return `${d.getMonth() + 1}/${d.getDate()}`;
  }

  formatDuration(s: number): string {
    if (s < 60) return `${Math.round(s)}s`;
    return `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
  }
}
