import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';

import { VoiceCampaignService } from './voice-campaign.service';
import {
  VoiceCampaign, VoiceCampaignRecipient, VoiceCampaignRecipientStatus,
} from './voice-campaign.models';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent, ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

const RETRYABLE: VoiceCampaignRecipientStatus[] = ['failed', 'no_answer', 'busy'];
const STATUS_ORDER: VoiceCampaignRecipientStatus[] = [
  'queued', 'processing', 'ready', 'calling', 'answered',
  'completed', 'no_answer', 'busy', 'failed',
];

@Component({
  selector: 'app-voice-campaign-detail',
  standalone: true,
  imports: [
    DatePipe, DecimalPipe, RouterLink, MatCardModule, MatTableModule, MatButtonModule,
    MatIconModule, MatTabsModule, MatProgressBarModule, MatTooltipModule,
  ],
  template: `
    <a mat-button routerLink="/voice-campaigns"><mat-icon>arrow_back</mat-icon> Voice Campaigns</a>
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (campaign(); as c) {
      <header class="head">
        <div><h1>{{ c.name }}</h1><span class="chip chip--{{ c.status }}">{{ c.status.replace('_', ' ') }}</span></div>
        <div class="actions">
          @if (c.status === 'draft') {
            <button mat-stroked-button [routerLink]="['/voice-campaigns', c.id, 'edit']"><mat-icon>edit</mat-icon> Edit draft</button>
          }
          @if (c.status === 'draft' || c.status === 'scheduled' || c.status === 'processing') {
            <button mat-stroked-button color="warn" (click)="cancel(c)"><mat-icon>cancel</mat-icon> Cancel</button>
          }
        </div>
      </header>

      @if (c.error_message) {
        <mat-card appearance="outlined" class="error-card"><mat-icon>error</mat-icon> {{ c.error_message }}</mat-card>
      }

      <div class="kpis">
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ c.total_recipients }}</span><span class="lbl">Recipients</span></div></mat-card>
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ c.estimated_tts_characters | number }}</span><span class="lbl">TTS characters reserved</span></div></mat-card>
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ consumedCharacters() | number }}</span><span class="lbl">TTS characters consumed so far</span></div></mat-card>
      </div>

      @if (c.status !== 'draft') {
        <div class="status-breakdown">
          @for (s of statusCounts(); track s.status) {
            @if (s.count > 0) {
              <span class="chip chip--{{ s.status }}">{{ s.count }} {{ s.status.replace('_', ' ') }}</span>
            }
          }
        </div>
      }

      <mat-tab-group (selectedTabChange)="onTab($event.index)">
        <mat-tab label="Overview">
          <div class="overview">
            <div><span class="k">Status</span><span>{{ c.status.replace('_', ' ') }}</span></div>
            <div><span class="k">Scheduled</span><span>{{ c.scheduled_at ? (c.scheduled_at | date: 'medium') : '—' }}</span></div>
            <div><span class="k">Started</span><span>{{ c.started_at ? (c.started_at | date: 'medium') : 'Not started yet' }}</span></div>
            <div><span class="k">Completed</span><span>{{ c.completed_at ? (c.completed_at | date: 'medium') : '—' }}</span></div>
            <div><span class="k">Created</span><span>{{ c.created_at | date: 'medium' }}</span></div>
          </div>
        </mat-tab>
        <mat-tab label="Recipients">
          @if (recipients().length === 0) { <p class="muted">No recipient snapshot yet — recipients are frozen when the campaign starts.</p> }
          @if (recipients().length > 0) {
            <table mat-table [dataSource]="recipients()">
              <ng-container matColumnDef="name"><th mat-header-cell *matHeaderCellDef>Name</th><td mat-cell *matCellDef="let r">{{ r.resolved_name || '—' }}</td></ng-container>
              <ng-container matColumnDef="phone"><th mat-header-cell *matHeaderCellDef>Phone</th><td mat-cell *matCellDef="let r">{{ r.phone_e164 }}</td></ng-container>
              <ng-container matColumnDef="text"><th mat-header-cell *matHeaderCellDef>Rendered text</th><td mat-cell *matCellDef="let r" class="content">{{ r.rendered_text }}</td></ng-container>
              <ng-container matColumnDef="chars"><th mat-header-cell *matHeaderCellDef>Characters</th><td mat-cell *matCellDef="let r">{{ r.tts_char_count }}{{ r.audio_id ? '' : ' (not yet synthesized)' }}</td></ng-container>
              <ng-container matColumnDef="status"><th mat-header-cell *matHeaderCellDef>Status</th><td mat-cell *matCellDef="let r">
                <span class="chip chip--{{ r.status }}">{{ r.status.replace('_', ' ') }}</span>
                @if (r.error_message) { <span class="err" [matTooltip]="r.error_message"><mat-icon>info</mat-icon></span> }
              </td></ng-container>
              <ng-container matColumnDef="actions"><th mat-header-cell *matHeaderCellDef></th><td mat-cell *matCellDef="let r">
                @if (isRetryable(r)) {
                  <button mat-icon-button matTooltip="Retry this recipient" (click)="retry(r)"><mat-icon>replay</mat-icon></button>
                }
              </td></ng-container>
              <tr mat-header-row *matHeaderRowDef="rcols"></tr>
              <tr mat-row *matRowDef="let row; columns: rcols"></tr>
            </table>
          }
        </mat-tab>
      </mat-tab-group>
    }
  `,
  styles: [`
    .head { display: flex; align-items: flex-start; justify-content: space-between; margin: .5rem 0 1rem; gap: 1rem; }
    .head h1 { margin: 0 0 .5rem; } .actions { display: flex; gap: .5rem; flex-wrap: wrap; }
    .error-card { display: flex; align-items: center; gap: .5rem; margin-bottom: 1rem; padding: .75rem 1rem; color: var(--mat-sys-error); }
    .kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1rem; max-width: 640px; }
    .kpi { display: flex; flex-direction: column; align-items: center; padding: 1rem; }
    .kpi .num { font-size: 1.6rem; font-weight: 600; } .kpi .lbl { color: var(--mat-sys-on-surface-variant); font-size: .8rem; text-align: center; }
    .status-breakdown { display: flex; gap: .4rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
    .overview { display: flex; flex-direction: column; gap: .75rem; padding: 1.5rem .5rem; }
    .overview > div { display: flex; gap: 1rem; } .overview .k { width: 120px; color: var(--mat-sys-on-surface-variant); }
    table { width: 100%; } .content { max-width: 320px; white-space: normal; }
    .muted { color: var(--mat-sys-on-surface-variant); padding: 1.5rem .5rem; }
    .err { color: var(--mat-sys-error); vertical-align: middle; cursor: help; margin-left: .3rem; }
    .err mat-icon { font-size: 1rem; height: 1rem; width: 1rem; vertical-align: middle; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--completed, .chip--ready, .chip--answered { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--scheduled, .chip--processing, .chip--partially_completed, .chip--queued, .chip--calling { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
    .chip--failed, .chip--cancelled, .chip--no_answer, .chip--busy { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
  `],
})
export class VoiceCampaignDetailComponent {
  private readonly api = inject(VoiceCampaignService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly rcols = ['name', 'phone', 'text', 'chars', 'status', 'actions'];
  readonly campaign = signal<VoiceCampaign | null>(null);
  readonly recipients = signal<VoiceCampaignRecipient[]>([]);
  readonly loading = signal(false);
  private id = '';

  // Client-side tallies from the currently-loaded recipient snapshot. The
  // Recipients tab loads with a page size covering the whole campaign (see
  // loadRecipients), so for any campaign of reasonable size this is an
  // accurate full breakdown, not just "this page" — a dedicated summary
  // endpoint would be the more scalable answer for very large campaigns,
  // not built here to keep this phase's API surface to what execution
  // actually needs.
  readonly statusCounts = computed(() => {
    const counts = new Map<VoiceCampaignRecipientStatus, number>();
    for (const r of this.recipients()) counts.set(r.status, (counts.get(r.status) ?? 0) + 1);
    return STATUS_ORDER.map((status) => ({ status, count: counts.get(status) ?? 0 }));
  });
  readonly consumedCharacters = computed(() =>
    this.recipients().filter((r) => r.audio_id).reduce((sum, r) => sum + r.tts_char_count, 0),
  );

  constructor() {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }
  load(): void {
    this.loading.set(true);
    this.api.getCampaign(this.id).subscribe({
      next: (c) => { this.campaign.set(c); this.loading.set(false); if (c.total_recipients > 0) this.loadRecipients(); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load campaign.'); },
    });
  }
  loadRecipients(): void {
    const size = Math.max(this.campaign()?.total_recipients ?? 50, 50);
    this.api.campaignRecipients(this.id, { size }).subscribe((r) => this.recipients.set(r.data));
  }
  onTab(i: number): void { if (i === 1) this.loadRecipients(); }

  isRetryable(r: VoiceCampaignRecipient): boolean { return RETRYABLE.includes(r.status); }

  retry(r: VoiceCampaignRecipient): void {
    this.api.retryRecipient(this.id, r.id).subscribe({
      next: () => { this.notify.success('Recipient queued for retry.'); this.load(); this.loadRecipients(); },
      error: () => this.notify.error('Unable to retry this recipient.'),
    });
  }

  cancel(c: VoiceCampaign): void {
    const data: ConfirmDialogData = {
      title: 'Cancel voice campaign',
      message: `Cancel "${c.name}"? Any reserved TTS quota will be released.`,
      confirmText: 'Cancel campaign', destructive: true,
    };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.api.cancelCampaign(c.id).subscribe({
        next: () => { this.notify.success('Campaign cancelled.'); this.load(); },
        error: () => this.notify.error('Unable to cancel campaign.'),
      });
    });
  }
}
