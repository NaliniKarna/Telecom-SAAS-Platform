import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { SmsService } from './sms.service';
import {
  AnalyticsOverview, AnalyticsTimePoint, AnalyticsFilters,
  SmsCampaignListItem, SmsSenderId,
} from './sms.models';
import { NotificationService } from '../../core/services/notification.service';

interface Bar { date: string; total: number; delivered: number; failed: number; dh: number; fh: number; }

@Component({
  selector: 'app-sms-analytics',
  standalone: true,
  imports: [
    FormsModule, MatCardModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatButtonModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>SMS Analytics</h1><p>Delivery performance across your campaigns.</p></div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>From</mat-label>
        <input matInput type="date" [(ngModel)]="since" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>To</mat-label>
        <input matInput type="date" [(ngModel)]="until" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Campaign</mat-label>
        <mat-select [(ngModel)]="campaignId">
          <mat-option [value]="null">All campaigns</mat-option>
          @for (c of campaigns(); track c.id) { <mat-option [value]="c.id">{{ c.name }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Sender ID</mat-label>
        <mat-select [(ngModel)]="senderValue">
          <mat-option [value]="null">All senders</mat-option>
          @for (s of senders(); track s.id) { <mat-option [value]="s.sender_id">{{ s.sender_id }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <button mat-flat-button color="primary" (click)="apply()"><mat-icon>filter_alt</mat-icon> Apply</button>
      <button mat-stroked-button (click)="reset()">Reset</button>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (overview(); as o) {
      <section class="widgets">
        <mat-card appearance="outlined"><div class="w"><span class="n">{{ o.total_messages }}</span><span class="l">Total Messages</span></div></mat-card>
        <mat-card appearance="outlined"><div class="w"><span class="n ok">{{ o.delivered_messages }}</span><span class="l">Delivered</span></div></mat-card>
        <mat-card appearance="outlined"><div class="w"><span class="n bad">{{ o.failed_messages }}</span><span class="l">Failed</span></div></mat-card>
        <mat-card appearance="outlined"><div class="w"><span class="n">{{ o.delivery_rate }}%</span><span class="l">Delivery Rate</span></div></mat-card>
        <mat-card appearance="outlined"><div class="w"><span class="n">{{ o.campaign_count }}</span><span class="l">Campaigns</span></div></mat-card>
        <mat-card appearance="outlined"><div class="w"><span class="n">{{ o.active_campaigns }}</span><span class="l">Active Campaigns</span></div></mat-card>
      </section>
    }

    <mat-card appearance="outlined" class="chart-card">
      <h2>Daily delivery</h2>
      @if (bars().length === 0) {
        <p class="muted">No message activity for the selected filters.</p>
      } @else {
        <svg [attr.viewBox]="'0 0 ' + chartW() + ' 220'" class="chart" preserveAspectRatio="xMidYMid meet">
          <line x1="40" y1="180" [attr.x2]="chartW() - 10" y2="180" class="axis" />
          @for (b of bars(); track b.date; let i = $index) {
            <rect [attr.x]="40 + i * group() + 6" [attr.y]="180 - b.dh" [attr.width]="barW()" [attr.height]="b.dh" class="bar bar--ok" />
            <rect [attr.x]="40 + i * group() + 6 + barW()" [attr.y]="180 - b.fh" [attr.width]="barW()" [attr.height]="b.fh" class="bar bar--bad" />
            <text [attr.x]="40 + i * group() + 6 + barW()" y="195" class="lbl" text-anchor="middle">{{ shortDate(b.date) }}</text>
          }
        </svg>
        <div class="legend">
          <span><i class="sw sw--ok"></i> Delivered</span>
          <span><i class="sw sw--bad"></i> Failed</span>
        </div>
      }
    </mat-card>
  `,
  styles: [`
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0 0 1rem; color: var(--mat-sys-on-surface-variant); }
    .filters { display: flex; gap: .75rem; flex-wrap: wrap; align-items: center; margin-bottom: 1rem; }
    .widgets { display: grid; grid-template-columns: repeat(6, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    @media (max-width: 1100px) { .widgets { grid-template-columns: repeat(3, 1fr); } }
    .w { display: flex; flex-direction: column; align-items: center; padding: 1rem .5rem; }
    .w .n { font-size: 1.6rem; font-weight: 600; } .w .n.ok { color: var(--mat-sys-primary); } .w .n.bad { color: var(--mat-sys-error); }
    .w .l { color: var(--mat-sys-on-surface-variant); font-size: .78rem; text-align: center; }
    .chart-card { padding: 1rem 1.25rem; } .chart-card h2 { margin: 0 0 1rem; font-size: 1.05rem; }
    .chart { width: 100%; height: 240px; } .axis { stroke: var(--mat-sys-outline-variant); }
    .bar--ok { fill: var(--mat-sys-primary); } .bar--bad { fill: var(--mat-sys-error); }
    .lbl { font-size: 9px; fill: var(--mat-sys-on-surface-variant); }
    .legend { display: flex; gap: 1.5rem; justify-content: center; margin-top: .5rem; color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .sw { display: inline-block; width: 10px; height: 10px; border-radius: 2px; margin-right: .3rem; }
    .sw--ok { background: var(--mat-sys-primary); } .sw--bad { background: var(--mat-sys-error); }
    .muted { color: var(--mat-sys-on-surface-variant); }
  `],
})
export class SmsAnalyticsComponent {
  private readonly api = inject(SmsService);
  private readonly notify = inject(NotificationService);

  readonly overview = signal<AnalyticsOverview | null>(null);
  readonly series = signal<AnalyticsTimePoint[]>([]);
  readonly campaigns = signal<SmsCampaignListItem[]>([]);
  readonly senders = signal<SmsSenderId[]>([]);
  readonly loading = signal(false);

  since: string | null = null;
  until: string | null = null;
  campaignId: string | null = null;
  senderValue: string | null = null;

  readonly bars = computed<Bar[]>(() => {
    const s = this.series();
    const max = Math.max(1, ...s.map((p) => p.total));
    return s.map((p) => ({
      date: p.date, total: p.total, delivered: p.delivered, failed: p.failed,
      dh: Math.round((p.delivered / max) * 150),
      fh: Math.round((p.failed / max) * 150),
    }));
  });
  readonly group = computed(() => Math.max(40, Math.min(80, Math.floor(700 / Math.max(1, this.bars().length)))));
  readonly barW = computed(() => Math.floor((this.group() - 12) / 2));
  readonly chartW = computed(() => Math.max(700, 40 + this.bars().length * this.group() + 10));

  constructor() {
    this.api.listCampaigns({ size: 100 }).subscribe((r) => this.campaigns.set(r.data));
    this.api.listSenderIds({ size: 100 }).subscribe((r) => this.senders.set(r.data));
    this.load();
  }

  private filters(): AnalyticsFilters {
    return {
      campaign_id: this.campaignId,
      sender_id: this.senderValue,
      since: this.since ? new Date(this.since).toISOString() : null,
      until: this.until ? new Date(this.until + 'T23:59:59').toISOString() : null,
    };
  }
  load(): void {
    this.loading.set(true);
    const f = this.filters();
    this.api.analyticsOverview(f).subscribe({
      next: (o) => { this.overview.set(o); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load analytics.'); },
    });
    this.api.analyticsTimeseries(f).subscribe({ next: (s) => this.series.set(s), error: () => {} });
  }
  apply(): void { this.load(); }
  reset(): void { this.since = this.until = this.campaignId = this.senderValue = null; this.load(); }
  shortDate(d: string): string { return d.slice(5); }
}
