import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatDialog } from '@angular/material/dialog';

import { ApiKeyService } from './api-key.service';
import { ApiKey } from './api-key.models';
import { ApiKeyGenerateDialogComponent } from './api-key-generate-dialog.component';
import { ApiKeyRevealDialogComponent } from './api-key-reveal-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-api-key-list',
  standalone: true,
  imports: [
    DatePipe, MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatProgressBarModule, MatMenuModule, MatTooltipModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>API Keys</h1>
        <p>Generate keys for programmatic access. Keys are shown once at creation.</p>
      </div>
      <button mat-flat-button color="primary" (click)="generate()">
        <mat-icon>add</mat-icon> Generate key
      </button>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (!loading() && rows().length === 0) {
      <div class="empty">
        <mat-icon>vpn_key</mat-icon>
        <p>No API keys yet. Generate one to enable programmatic access.</p>
      </div>
    }

    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let k">
              <div class="name">{{ k.name }}</div>
              <code class="prefix">{{ k.key_prefix }}…</code>
            </td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let k"><span class="chip chip--{{ k.status }}">{{ k.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="usage">
            <th mat-header-cell *matHeaderCellDef>Usage</th>
            <td mat-cell *matCellDef="let k">{{ k.usage_count }}</td>
          </ng-container>
          <ng-container matColumnDef="lastUsed">
            <th mat-header-cell *matHeaderCellDef>Last used</th>
            <td mat-cell *matCellDef="let k">{{ k.last_used_at ? (k.last_used_at | date: 'medium') : 'Never' }}</td>
          </ng-container>
          <ng-container matColumnDef="expires">
            <th mat-header-cell *matHeaderCellDef>Expires</th>
            <td mat-cell *matCellDef="let k">{{ k.expires_at ? (k.expires_at | date: 'mediumDate') : 'Never' }}</td>
          </ng-container>
          <ng-container matColumnDef="ipWhitelist">
            <th mat-header-cell *matHeaderCellDef>IP whitelist</th>
            <td mat-cell *matCellDef="let k">
              @if (k.ip_whitelist?.length) {
                <span class="ip-chips" [matTooltip]="k.ip_whitelist.join(', ')">
                  {{ k.ip_whitelist.length }} {{ k.ip_whitelist.length === 1 ? 'entry' : 'entries' }}
                </span>
              } @else {
                <span class="ip-any">Any IP</span>
              }
            </td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let k">
              @if (k.status === 'active') {
                <button mat-icon-button [matMenuTriggerFor]="menu" aria-label="Actions"><mat-icon>more_vert</mat-icon></button>
                <mat-menu #menu="matMenu">
                  <button mat-menu-item (click)="revoke(k)"><mat-icon>block</mat-icon><span>Revoke</span></button>
                </mat-menu>
              }
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
      </mat-card>
    }
  `,
  styles: [
    `
      .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      table { width: 100%; }
      .name { font-weight: 500; }
      .prefix { font-family: monospace; color: var(--mat-sys-on-surface-variant); font-size: 0.8rem; }
      .chip { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .chip--revoked { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
      .chip--expired { background: var(--mat-sys-surface-container-highest); color: var(--mat-sys-on-surface-variant); }
      .ip-chips { font-family: monospace; font-size: 0.8rem; border-bottom: 1px dashed var(--mat-sys-on-surface-variant); cursor: default; }
      .ip-any { color: var(--mat-sys-on-surface-variant); font-size: 0.85rem; }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
    `,
  ],
})
export class ApiKeyListComponent {
  private readonly api = inject(ApiKeyService);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly cols = ['name', 'status', 'usage', 'lastUsed', 'expires', 'ipWhitelist', 'actions'];
  readonly rows = signal<ApiKey[]>([]);
  readonly loading = signal(false);

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.list().subscribe({
      next: (res) => { this.rows.set(res.data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  generate(): void {
    this.dialog.open(ApiKeyGenerateDialogComponent, { autoFocus: false })
      .afterClosed().subscribe((created) => {
        if (!created) return;
        // Show the plaintext key ONCE, then refresh the list.
        this.dialog.open(ApiKeyRevealDialogComponent, { data: created, disableClose: true, autoFocus: false })
          .afterClosed().subscribe(() => this.load());
      });
  }

  revoke(k: ApiKey): void {
    this.api.revoke(k.id).subscribe({
      next: () => { this.notify.success(`Revoked "${k.name}".`); this.load(); },
    });
  }
}
