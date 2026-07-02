import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
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

import { SmsService } from './sms.service';
import { SmsCampaignListItem, CampaignStatus } from './sms.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-campaign-list',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatPaginatorModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>SMS Campaigns</h1><p>Create, schedule and send SMS campaigns to your contacts.</p></div>
      <button mat-flat-button color="primary" (click)="create()"><mat-icon>add</mat-icon> New campaign</button>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline" class="search">
        <mat-icon matPrefix>search</mat-icon>
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="applyFilters()" placeholder="Campaign name" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="draft">Draft</mat-option>
          <mat-option value="scheduled">Scheduled</mat-option>
          <mat-option value="processing">Processing</mat-option>
          <mat-option value="completed">Completed</mat-option>
          <mat-option value="cancelled">Cancelled</mat-option>
          <mat-option value="failed">Failed</mat-option>
        </mat-select>
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>campaign</mat-icon><p>No campaigns yet.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let c"><strong>{{ c.name }}</strong></td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let c"><span class="chip chip--{{ c.status }}">{{ c.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="source">
            <th mat-header-cell *matHeaderCellDef>Source</th>
            <td mat-cell *matCellDef="let c">{{ c.source_type === 'contact_list' ? 'List' : 'Contacts' }}</td>
          </ng-container>
          <ng-container matColumnDef="recipients">
            <th mat-header-cell *matHeaderCellDef>Recipients</th>
            <td mat-cell *matCellDef="let c">{{ c.total_recipients }}</td>
          </ng-container>
          <ng-container matColumnDef="delivered">
            <th mat-header-cell *matHeaderCellDef>Sent / Failed</th>
            <td mat-cell *matCellDef="let c">{{ c.sent_count }} / {{ c.failed_count }}</td>
          </ng-container>
          <ng-container matColumnDef="schedule">
            <th mat-header-cell *matHeaderCellDef>Schedule</th>
            <td mat-cell *matCellDef="let c">{{ c.schedule_time ? (c.schedule_time | date: 'short') : '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="created">
            <th mat-header-cell *matHeaderCellDef>Created</th>
            <td mat-cell *matCellDef="let c">{{ c.created_at | date: 'mediumDate' }}</td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols" class="clickable" (click)="open(row)"></tr>
        </table>
        <mat-paginator [length]="total()" [pageSize]="size" [pageIndex]="page - 1"
          [pageSizeOptions]="[10, 20, 50]" (page)="onPage($event)" />
      </mat-card>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; gap: 1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); }
    .filters { display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; } .filters .search { flex: 1 1 280px; }
    table { width: 100%; } .clickable { cursor: pointer; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--completed { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--scheduled, .chip--processing { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
    .chip--failed, .chip--cancelled { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class SmsCampaignListComponent {
  private readonly api = inject(SmsService);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  readonly cols = ['name', 'status', 'source', 'recipients', 'delivered', 'schedule', 'created'];
  readonly rows = signal<SmsCampaignListItem[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  search = '';
  statusFilter: CampaignStatus | null = null;
  page = 1;
  size = 20;

  constructor() { this.load(); }
  load(): void {
    this.loading.set(true);
    this.api.listCampaigns({ search: this.search || undefined, status: this.statusFilter, page: this.page, size: this.size }).subscribe({
      next: (res) => { this.rows.set(res.data); this.total.set(res.meta.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load campaigns.'); },
    });
  }
  applyFilters(): void { this.page = 1; this.load(); }
  onPage(e: PageEvent): void { this.page = e.pageIndex + 1; this.size = e.pageSize; this.load(); }
  create(): void { this.router.navigate(['/sms/campaigns/new']); }
  open(c: SmsCampaignListItem): void { this.router.navigate(['/sms/campaigns', c.id]); }
}
