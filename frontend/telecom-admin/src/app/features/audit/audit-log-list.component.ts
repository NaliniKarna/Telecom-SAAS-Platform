import { Component, inject, signal } from '@angular/core';
import { DatePipe, JsonPipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatExpansionModule } from '@angular/material/expansion';

import { AuditService } from './audit.service';
import { AuditLog, AuditQuery } from './audit.models';

@Component({
  selector: 'app-audit-log-list',
  standalone: true,
  imports: [
    DatePipe,
    JsonPipe,
    FormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatExpansionModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Audit Logs</h1>
        <p>Platform-wide activity trail.</p>
      </div>
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    <div class="filters">
      <mat-form-field appearance="outline" class="f-search">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="q.search" (keyup.enter)="apply()"
          placeholder="Action, module, description" />
        <mat-icon matSuffix>search</mat-icon>
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>Action</mat-label>
        <mat-select [(ngModel)]="q.action" (selectionChange)="apply()">
          <mat-option [value]="undefined">All</mat-option>
          @for (a of actions(); track a) {
            <mat-option [value]="a">{{ a }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>Module</mat-label>
        <mat-select [(ngModel)]="q.entity_type" (selectionChange)="apply()">
          <mat-option [value]="undefined">All</mat-option>
          @for (m of modules(); track m) {
            <mat-option [value]="m">{{ m }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>From</mat-label>
        <input matInput type="date" [(ngModel)]="dateFrom" (change)="apply()" />
      </mat-form-field>

      <mat-form-field appearance="outline">
        <mat-label>To</mat-label>
        <input matInput type="date" [(ngModel)]="dateTo" (change)="apply()" />
      </mat-form-field>

      <button mat-stroked-button (click)="reset()">Clear</button>
    </div>

    <div class="table-wrap">
      <table mat-table [dataSource]="rows()" multiTemplateDataRows>
        <ng-container matColumnDef="time">
          <th mat-header-cell *matHeaderCellDef>Time</th>
          <td mat-cell *matCellDef="let r">{{ r.created_at | date: 'short' }}</td>
        </ng-container>
        <ng-container matColumnDef="actor">
          <th mat-header-cell *matHeaderCellDef>Actor</th>
          <td mat-cell *matCellDef="let r">{{ r.actor_name ?? r.actor_email ?? 'System' }}</td>
        </ng-container>
        <ng-container matColumnDef="action">
          <th mat-header-cell *matHeaderCellDef>Action</th>
          <td mat-cell *matCellDef="let r"><span class="chip">{{ r.action }}</span></td>
        </ng-container>
        <ng-container matColumnDef="module">
          <th mat-header-cell *matHeaderCellDef>Module</th>
          <td mat-cell *matCellDef="let r">{{ r.entity_type }}</td>
        </ng-container>
        <ng-container matColumnDef="company">
          <th mat-header-cell *matHeaderCellDef>Company</th>
          <td mat-cell *matCellDef="let r">{{ r.company_name ?? '—' }}</td>
        </ng-container>
        <ng-container matColumnDef="ip">
          <th mat-header-cell *matHeaderCellDef>IP</th>
          <td mat-cell *matCellDef="let r">{{ r.ip_address ?? '—' }}</td>
        </ng-container>

        <!-- expandable detail row -->
        <ng-container matColumnDef="expand">
          <td mat-cell *matCellDef="let r" [attr.colspan]="columns.length">
            <div class="detail" [class.detail--open]="expanded() === r.id">
              @if (expanded() === r.id) {
                <div class="detail__grid">
                  <div><strong>Entity ID</strong><span>{{ r.entity_id ?? '—' }}</span></div>
                  <div><strong>Description</strong><span>{{ r.description ?? '—' }}</span></div>
                  <div><strong>Actor email</strong><span>{{ r.actor_email ?? '—' }}</span></div>
                </div>
                @if (r.old_values || r.new_values) {
                  <div class="values">
                    <div>
                      <strong>Before</strong>
                      <pre>{{ r.old_values ? (r.old_values | json) : '—' }}</pre>
                    </div>
                    <div>
                      <strong>After</strong>
                      <pre>{{ r.new_values ? (r.new_values | json) : '—' }}</pre>
                    </div>
                  </div>
                }
              }
            </div>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns"
          class="clickable" (click)="toggle(row)"></tr>
        <tr mat-row *matRowDef="let row; columns: ['expand']" class="detail-row"></tr>
      </table>

      @if (!loading() && rows().length === 0) {
        <div class="empty">No audit entries match these filters.</div>
      }
    </div>

    <mat-paginator
      [length]="total()"
      [pageSize]="size()"
      [pageIndex]="page() - 1"
      [pageSizeOptions]="[25, 50, 100]"
      (page)="onPage($event)"
    />
  `,
  styles: [
    `
      .page-header { margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .filters {
        display: flex; gap: 0.75rem; align-items: center;
        margin-bottom: 1rem; flex-wrap: wrap;
      }
      .f-search { flex: 1 1 240px; }
      .table-wrap {
        background: var(--mat-sys-surface-container-low);
        border: 1px solid var(--mat-sys-outline-variant);
        border-radius: 12px; overflow: hidden;
      }
      table { width: 100%; background: transparent; }
      .clickable { cursor: pointer; }
      .chip {
        text-transform: capitalize; padding: 0.1rem 0.55rem;
        border-radius: 999px; font: var(--mat-sys-label-small);
        background: var(--mat-sys-secondary-container);
        color: var(--mat-sys-on-secondary-container);
      }
      .detail-row td { padding: 0 !important; border: none; }
      .detail-row { height: 0; }
      .detail { max-height: 0; overflow: hidden; transition: max-height 0.2s ease; }
      .detail--open { max-height: 600px; padding: 1rem 1.25rem; }
      .detail__grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.75rem; margin-bottom: 0.75rem;
      }
      .detail__grid strong, .values strong {
        display: block; color: var(--mat-sys-on-surface-variant);
        font: var(--mat-sys-label-small);
      }
      .values { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
      pre {
        margin: 0.25rem 0 0; padding: 0.5rem; border-radius: 8px;
        background: var(--mat-sys-surface-container);
        font-size: 0.8rem; overflow-x: auto; white-space: pre-wrap;
      }
      .empty {
        padding: 2rem; text-align: center;
        color: var(--mat-sys-on-surface-variant);
      }
    `,
  ],
})
export class AuditLogListComponent {
  private readonly api = inject(AuditService);

  readonly columns = ['time', 'actor', 'action', 'module', 'company', 'ip'];
  readonly rows = signal<AuditLog[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(25);
  readonly loading = signal(false);
  readonly expanded = signal<number | null>(null);
  readonly actions = signal<string[]>([]);
  readonly modules = signal<string[]>([]);

  // Bound filter state.
  q: AuditQuery = {};
  dateFrom = '';
  dateTo = '';

  constructor() {
    this.api.facets().subscribe({
      next: (f) => {
        this.actions.set(f.actions);
        this.modules.set(f.modules);
      },
    });
    this.load();
  }

  load(): void {
    this.loading.set(true);
    const query: AuditQuery = {
      ...this.q,
      page: this.page(),
      size: this.size(),
      date_from: this.dateFrom ? new Date(this.dateFrom).toISOString() : undefined,
      date_to: this.dateTo
        ? new Date(this.dateTo + 'T23:59:59').toISOString()
        : undefined,
    };
    this.api.list(query).subscribe({
      next: (res) => {
        this.rows.set(res.data);
        this.total.set(res.meta.total);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  apply(): void {
    this.page.set(1);
    this.load();
  }

  reset(): void {
    this.q = {};
    this.dateFrom = '';
    this.dateTo = '';
    this.page.set(1);
    this.load();
  }

  onPage(e: PageEvent): void {
    this.page.set(e.pageIndex + 1);
    this.size.set(e.pageSize);
    this.load();
  }

  toggle(r: AuditLog): void {
    this.expanded.set(this.expanded() === r.id ? null : r.id);
  }
}
