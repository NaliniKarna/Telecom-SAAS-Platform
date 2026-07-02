import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { SmsService } from './sms.service';
import { CampaignMessage, MessageStatus, SmsCampaignListItem } from './sms.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-messages',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatPaginatorModule, MatProgressBarModule,
    MatTooltipModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>SMS Messages</h1><p>Every generated message and its delivery status.</p></div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Campaign</mat-label>
        <mat-select [(ngModel)]="campaignId" (selectionChange)="applyFilters()">
          <mat-option [value]="null">All</mat-option>
          @for (c of campaigns(); track c.id) { <mat-option [value]="c.id">{{ c.name }}</mat-option> }
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="queued">Queued</mat-option>
          <mat-option value="sent">Sent</mat-option>
          <mat-option value="delivered">Delivered</mat-option>
          <mat-option value="failed">Failed</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Sender ID</mat-label>
        <input matInput [(ngModel)]="senderValue" (keyup.enter)="applyFilters()" placeholder="e.g. ACME" />
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>inbox</mat-icon><p>No messages match your filters.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="recipient">
            <th mat-header-cell *matHeaderCellDef>Recipient</th>
            <td mat-cell *matCellDef="let m">{{ m.recipient_phone }}</td>
          </ng-container>
          <ng-container matColumnDef="sender">
            <th mat-header-cell *matHeaderCellDef>Sender</th>
            <td mat-cell *matCellDef="let m">{{ m.sender_id || '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="content">
            <th mat-header-cell *matHeaderCellDef>Content</th>
            <td mat-cell *matCellDef="let m" class="content">{{ m.content }}</td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let m">
              <span class="chip chip--{{ m.status }}">{{ m.status }}</span>
              @if (m.error_details) { <mat-icon class="err" [matTooltip]="m.error_details">error</mat-icon> }
            </td>
          </ng-container>
          <ng-container matColumnDef="provider">
            <th mat-header-cell *matHeaderCellDef>Provider ID</th>
            <td mat-cell *matCellDef="let m" class="pid">{{ m.provider_message_id || '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="sent">
            <th mat-header-cell *matHeaderCellDef>Sent</th>
            <td mat-cell *matCellDef="let m">{{ m.sent_at ? (m.sent_at | date: 'short') : '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="delivered">
            <th mat-header-cell *matHeaderCellDef>Delivered</th>
            <td mat-cell *matCellDef="let m">{{ m.delivered_at ? (m.delivered_at | date: 'short') : '—' }}</td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
        <mat-paginator [length]="total()" [pageSize]="size" [pageIndex]="page - 1"
          [pageSizeOptions]="[25, 50, 100]" (page)="onPage($event)" />
      </mat-card>
    }
  `,
  styles: [`
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0 0 1rem; color: var(--mat-sys-on-surface-variant); }
    .filters { display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; }
    table { width: 100%; }
    .content { max-width: 280px; white-space: normal; color: var(--mat-sys-on-surface-variant); }
    .pid { font-family: monospace; font-size: .8rem; color: var(--mat-sys-on-surface-variant); }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--delivered { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--sent, .chip--queued { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
    .chip--failed { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .err { font-size: 1rem; height: 1rem; width: 1rem; vertical-align: middle; color: var(--mat-sys-error); cursor: help; margin-left: .25rem; }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class SmsMessagesComponent {
  private readonly api = inject(SmsService);
  private readonly notify = inject(NotificationService);

  readonly cols = ['recipient', 'sender', 'content', 'status', 'provider', 'sent', 'delivered'];
  readonly rows = signal<CampaignMessage[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  readonly campaigns = signal<SmsCampaignListItem[]>([]);
  campaignId: string | null = null;
  statusFilter: MessageStatus | null = null;
  senderValue = '';
  page = 1;
  size = 50;

  constructor() {
    this.api.listCampaigns({ size: 100 }).subscribe((r) => this.campaigns.set(r.data));
    this.load();
  }
  load(): void {
    this.loading.set(true);
    this.api.trackingMessages({
      campaign_id: this.campaignId, status: this.statusFilter,
      sender_id: this.senderValue || null, page: this.page, size: this.size,
    }).subscribe({
      next: (r) => { this.rows.set(r.data); this.total.set(r.meta.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load messages.'); },
    });
  }
  applyFilters(): void { this.page = 1; this.load(); }
  onPage(e: PageEvent): void { this.page = e.pageIndex + 1; this.size = e.pageSize; this.load(); }
}
