import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog } from '@angular/material/dialog';
import { RouterLink } from '@angular/router';

import { AdminAiVoiceService } from './admin-ai-voice.service';
import { AdminVoice, VoiceStatus } from './admin-ai-voice.models';
import { AdminVoiceEditDialogComponent } from './admin-voice-edit-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-admin-voice-list',
  standalone: true,
  imports: [
    RouterLink, FormsModule, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatMenuModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatPaginatorModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>AI Voices</h1><p>Platform-wide voice catalog. Availability per plan is set on each plan's page.</p></div>
      <div class="header-actions">
        <a mat-stroked-button routerLink="/admin/ai-voice/preview"><mat-icon>graphic_eq</mat-icon> Test a voice</a>
        <button mat-flat-button color="primary" (click)="create()"><mat-icon>add</mat-icon> New voice</button>
      </div>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline" class="search">
        <mat-icon matPrefix>search</mat-icon>
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="applyFilters()" placeholder="Name or description" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
        </mat-select>
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>graphic_eq</mat-icon><p>No voices match your filters.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let v">
              <strong>{{ v.name }}</strong>
              @if (v.description) { <div class="sub">{{ v.description }}</div> }
            </td>
          </ng-container>
          <ng-container matColumnDef="language">
            <th mat-header-cell *matHeaderCellDef>Language</th>
            <td mat-cell *matCellDef="let v">{{ v.language }}</td>
          </ng-container>
          <ng-container matColumnDef="gender">
            <th mat-header-cell *matHeaderCellDef>Gender</th>
            <td mat-cell *matCellDef="let v">{{ v.gender || '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="provider">
            <th mat-header-cell *matHeaderCellDef>Provider</th>
            <td mat-cell *matCellDef="let v">
              <span class="tag">{{ v.provider }}</span>
              <div class="sub mono">{{ v.provider_voice_id }}</div>
            </td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let v"><span class="chip chip--{{ v.status }}">{{ v.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let v">
              <button mat-icon-button [matMenuTriggerFor]="menu"><mat-icon>more_vert</mat-icon></button>
              <mat-menu #menu="matMenu">
                <button mat-menu-item (click)="edit(v)"><mat-icon>edit</mat-icon> Edit</button>
                @if (v.status === 'active') {
                  <button mat-menu-item (click)="deactivate(v)"><mat-icon>toggle_off</mat-icon> Deactivate</button>
                } @else {
                  <button mat-menu-item (click)="activate(v)"><mat-icon>toggle_on</mat-icon> Activate</button>
                }
              </mat-menu>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
        <mat-paginator [length]="total()" [pageSize]="size" [pageIndex]="page - 1"
          [pageSizeOptions]="[10, 20, 50]" (page)="onPage($event)" />
      </mat-card>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; gap: 1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); }
    .header-actions { display: flex; gap: .5rem; flex-wrap: wrap; }
    .filters { display: flex; gap: .75rem; flex-wrap: wrap; margin-bottom: 1rem; } .filters .search { flex: 1 1 280px; }
    table { width: 100%; }
    .sub { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .mono { font-family: monospace; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--inactive { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class AdminVoiceListComponent {
  private readonly api = inject(AdminAiVoiceService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly cols = ['name', 'language', 'gender', 'provider', 'status', 'actions'];
  readonly rows = signal<AdminVoice[]>([]);
  readonly total = signal(0);
  readonly loading = signal(false);
  search = '';
  statusFilter: VoiceStatus | null = null;
  page = 1;
  size = 20;

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.listVoices({ search: this.search || undefined, status: this.statusFilter, page: this.page, size: this.size }).subscribe({
      next: (res) => { this.rows.set(res.data); this.total.set(res.meta.total); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load voices.'); },
    });
  }
  applyFilters(): void { this.page = 1; this.load(); }
  onPage(e: PageEvent): void { this.page = e.pageIndex + 1; this.size = e.pageSize; this.load(); }

  create(): void {
    this.dialog.open(AdminVoiceEditDialogComponent, { autoFocus: false }).afterClosed().subscribe((v) => { if (v) this.load(); });
  }
  edit(v: AdminVoice): void {
    this.dialog.open(AdminVoiceEditDialogComponent, { autoFocus: false, data: { voice: v } }).afterClosed().subscribe((u) => { if (u) this.load(); });
  }
  activate(v: AdminVoice): void {
    this.api.activateVoice(v.id).subscribe({ next: () => { this.notify.success('Voice activated.'); this.load(); }, error: () => this.notify.error('Unable to activate voice.') });
  }
  deactivate(v: AdminVoice): void {
    this.api.deactivateVoice(v.id).subscribe({ next: () => { this.notify.success('Voice deactivated.'); this.load(); }, error: () => this.notify.error('Unable to deactivate voice.') });
  }
}
