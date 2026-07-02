import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatDialog, MatDialogModule, MatDialogRef } from '@angular/material/dialog';

import { SmsService } from './sms.service';
import { SmsCampaign, CampaignRecipient, CampaignMessage } from './sms.models';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent, ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-sms-schedule-dialog',
  standalone: true,
  imports: [FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Schedule campaign</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline" style="width: 320px;">
        <mat-label>Send at</mat-label>
        <input matInput type="datetime-local" [(ngModel)]="when" />
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(undefined)">Cancel</button>
      <button mat-flat-button color="primary" (click)="ref.close(when)" [disabled]="!when">Schedule</button>
    </mat-dialog-actions>
  `,
})
export class SmsScheduleDialogComponent {
  readonly ref = inject(MatDialogRef<SmsScheduleDialogComponent>);
  when = '';
}

@Component({
  selector: 'app-sms-campaign-detail',
  standalone: true,
  imports: [
    DatePipe, RouterLink, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatTabsModule, MatProgressBarModule,
  ],
  template: `
    <a mat-button routerLink="/sms/campaigns"><mat-icon>arrow_back</mat-icon> Campaigns</a>
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (campaign(); as c) {
      <header class="head">
        <div><h1>{{ c.name }}</h1><span class="chip chip--{{ c.status }}">{{ c.status }}</span></div>
        <div class="actions">
          @if (c.status === 'draft') {
            <button mat-stroked-button [routerLink]="['/sms/campaigns', c.id, 'edit']"><mat-icon>edit</mat-icon> Edit</button>
          }
          @if (c.status === 'draft' || c.status === 'scheduled') {
            <button mat-flat-button color="primary" (click)="send(c)"><mat-icon>send</mat-icon> Send now</button>
            <button mat-stroked-button (click)="schedule(c)"><mat-icon>schedule</mat-icon> Schedule</button>
            <button mat-stroked-button color="warn" (click)="cancel(c)"><mat-icon>cancel</mat-icon> Cancel</button>
          }
        </div>
      </header>

      <div class="kpis">
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ c.total_recipients }}</span><span class="lbl">Recipients</span></div></mat-card>
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ c.sent_count }}</span><span class="lbl">Sent</span></div></mat-card>
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ c.delivered_count }}</span><span class="lbl">Delivered</span></div></mat-card>
        <mat-card appearance="outlined"><div class="kpi"><span class="num">{{ c.failed_count }}</span><span class="lbl">Failed</span></div></mat-card>
      </div>

      <mat-tab-group (selectedTabChange)="onTab($event.index)">
        <mat-tab label="Overview">
          <div class="overview">
            <div><span class="k">Status</span><span>{{ c.status }}</span></div>
            <div><span class="k">Source</span><span>{{ c.source_type === 'contact_list' ? 'Contact list' : 'Individual contacts' }}</span></div>
            <div><span class="k">Scheduled</span><span>{{ c.schedule_time ? (c.schedule_time | date: 'medium') : '—' }}</span></div>
            <div><span class="k">Created</span><span>{{ c.created_at | date: 'medium' }}</span></div>
          </div>
        </mat-tab>
        <mat-tab label="Recipients">
          @if (recipients().length === 0) { <p class="muted">No recipients frozen yet.</p> }
          @if (recipients().length > 0) {
            <table mat-table [dataSource]="recipients()">
              <ng-container matColumnDef="name"><th mat-header-cell *matHeaderCellDef>Name</th><td mat-cell *matCellDef="let r">{{ r.resolved_name || '—' }}</td></ng-container>
              <ng-container matColumnDef="phone"><th mat-header-cell *matHeaderCellDef>Phone</th><td mat-cell *matCellDef="let r">{{ r.phone_e164 }}</td></ng-container>
              <tr mat-header-row *matHeaderRowDef="rcols"></tr>
              <tr mat-row *matRowDef="let row; columns: rcols"></tr>
            </table>
          }
        </mat-tab>
        <mat-tab label="Messages">
          @if (messages().length === 0) { <p class="muted">No messages yet. Send the campaign to generate message records.</p> }
          @if (messages().length > 0) {
            <table mat-table [dataSource]="messages()">
              <ng-container matColumnDef="phone"><th mat-header-cell *matHeaderCellDef>Recipient</th><td mat-cell *matCellDef="let m">{{ m.recipient_phone }}</td></ng-container>
              <ng-container matColumnDef="sender"><th mat-header-cell *matHeaderCellDef>Sender</th><td mat-cell *matCellDef="let m">{{ m.sender_id }}</td></ng-container>
              <ng-container matColumnDef="content"><th mat-header-cell *matHeaderCellDef>Content</th><td mat-cell *matCellDef="let m" class="content">{{ m.content }}</td></ng-container>
              <ng-container matColumnDef="status"><th mat-header-cell *matHeaderCellDef>Status</th><td mat-cell *matCellDef="let m"><span class="chip chip--{{ m.status }}">{{ m.status }}</span>@if (m.error_details) { <span class="err">{{ m.error_details }}</span> }</td></ng-container>
              <ng-container matColumnDef="sent"><th mat-header-cell *matHeaderCellDef>Sent</th><td mat-cell *matCellDef="let m">{{ m.sent_at ? (m.sent_at | date: 'short') : '—' }}</td></ng-container>
              <tr mat-header-row *matHeaderRowDef="mcols"></tr>
              <tr mat-row *matRowDef="let row; columns: mcols"></tr>
            </table>
          }
        </mat-tab>
      </mat-tab-group>
    }
  `,
  styles: [`
    .head { display: flex; align-items: flex-start; justify-content: space-between; margin: .5rem 0 1rem; gap: 1rem; }
    .head h1 { margin: 0 0 .5rem; } .actions { display: flex; gap: .5rem; flex-wrap: wrap; }
    .kpis { display: grid; grid-template-columns: repeat(4, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
    .kpi { display: flex; flex-direction: column; align-items: center; padding: 1rem; }
    .kpi .num { font-size: 1.6rem; font-weight: 600; } .kpi .lbl { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .overview { display: flex; flex-direction: column; gap: .75rem; padding: 1.5rem .5rem; }
    .overview > div { display: flex; gap: 1rem; } .overview .k { width: 120px; color: var(--mat-sys-on-surface-variant); }
    table { width: 100%; } .content { max-width: 320px; white-space: normal; }
    .muted { color: var(--mat-sys-on-surface-variant); padding: 1.5rem .5rem; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--completed, .chip--delivered { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--scheduled, .chip--processing, .chip--sent { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
    .chip--failed, .chip--cancelled { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .err { display: block; color: var(--mat-sys-error); font-size: .75rem; }
  `],
})
export class SmsCampaignDetailComponent {
  private readonly api = inject(SmsService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly rcols = ['name', 'phone'];
  readonly mcols = ['phone', 'sender', 'content', 'status', 'sent'];
  readonly campaign = signal<SmsCampaign | null>(null);
  readonly recipients = signal<CampaignRecipient[]>([]);
  readonly messages = signal<CampaignMessage[]>([]);
  readonly loading = signal(false);
  private id = '';

  constructor() {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }
  load(): void {
    this.loading.set(true);
    this.api.getCampaign(this.id).subscribe({
      next: (c) => { this.campaign.set(c); this.loading.set(false); this.loadRecipients(); this.loadMessages(); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load campaign.'); },
    });
  }
  loadRecipients(): void { this.api.campaignRecipients(this.id).subscribe((r) => this.recipients.set(r.data)); }
  loadMessages(): void { this.api.campaignMessages(this.id).subscribe((r) => this.messages.set(r.data)); }
  onTab(i: number): void { if (i === 1) this.loadRecipients(); if (i === 2) this.loadMessages(); }

  send(c: SmsCampaign): void {
    const data: ConfirmDialogData = { title: 'Send campaign', message: `Send "${c.name}" now? Messages will be dispatched immediately.`, confirmText: 'Send' };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.api.sendCampaign(c.id).subscribe({ next: () => { this.notify.success('Campaign sent.'); this.load(); }, error: () => this.notify.error('Unable to send.') });
    });
  }
  schedule(c: SmsCampaign): void {
    this.dialog.open(SmsScheduleDialogComponent, { autoFocus: false }).afterClosed().subscribe((when: string | undefined) => {
      if (!when) return;
      this.api.scheduleCampaign(c.id, new Date(when).toISOString()).subscribe({ next: () => { this.notify.success('Campaign scheduled.'); this.load(); }, error: () => this.notify.error('Unable to schedule.') });
    });
  }
  cancel(c: SmsCampaign): void {
    const data: ConfirmDialogData = { title: 'Cancel campaign', message: `Cancel "${c.name}"?`, confirmText: 'Cancel campaign', destructive: true };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.api.cancelCampaign(c.id).subscribe({ next: () => { this.notify.success('Campaign cancelled.'); this.load(); }, error: () => this.notify.error('Unable to cancel.') });
    });
  }
}
