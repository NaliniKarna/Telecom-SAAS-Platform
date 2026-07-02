import { Component, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';

import { PlansService } from './plans.service';
import { PlanListItem } from './plan.models';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-plan-list',
  standalone: true,
  imports: [
    RouterLink,
    FormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatMenuModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Subscription Plans</h1>
        <p>Define the limits and entitlements available to companies.</p>
      </div>
      <button mat-flat-button color="primary" routerLink="/subscription-plans/new">
        <mat-icon>add</mat-icon>
        New plan
      </button>
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    <div class="filters">
      <mat-form-field appearance="outline" class="filters__search">
        <mat-label>Search</mat-label>
        <input
          matInput
          [(ngModel)]="search"
          (keyup.enter)="applyFilters()"
          placeholder="Name or code"
        />
        <mat-icon matSuffix>search</mat-icon>
      </mat-form-field>

      <mat-form-field appearance="outline" class="filters__status">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="''">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
        </mat-select>
      </mat-form-field>

      <button mat-stroked-button (click)="applyFilters()">Apply</button>
    </div>

    <div class="table-wrap">
      <table mat-table [dataSource]="rows()">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Name</th>
          <td mat-cell *matCellDef="let p">{{ p.name }}</td>
        </ng-container>
        <ng-container matColumnDef="code">
          <th mat-header-cell *matHeaderCellDef>Code</th>
          <td mat-cell *matCellDef="let p"><code>{{ p.code }}</code></td>
        </ng-container>
        <ng-container matColumnDef="usage">
          <th mat-header-cell *matHeaderCellDef>Companies</th>
          <td mat-cell *matCellDef="let p">{{ p.usage_count }}</td>
        </ng-container>
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef>Status</th>
          <td mat-cell *matCellDef="let p">
            <span class="status status--{{ p.is_active ? 'active' : 'inactive' }}">
              {{ p.is_active ? 'active' : 'inactive' }}
            </span>
          </td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let p">
            <button mat-icon-button [matMenuTriggerFor]="menu" (click)="$event.stopPropagation()">
              <mat-icon>more_vert</mat-icon>
            </button>
            <mat-menu #menu="matMenu">
              <button mat-menu-item [routerLink]="['/subscription-plans', p.id]">
                <mat-icon>visibility</mat-icon><span>View</span>
              </button>
              <button mat-menu-item [routerLink]="['/subscription-plans', p.id, 'edit']">
                <mat-icon>edit</mat-icon><span>Edit</span>
              </button>
              @if (p.is_active) {
                <button mat-menu-item (click)="deactivate(p)">
                  <mat-icon>block</mat-icon><span>Deactivate</span>
                </button>
              } @else {
                <button mat-menu-item (click)="activate(p)">
                  <mat-icon>check_circle</mat-icon><span>Activate</span>
                </button>
              }
              <button mat-menu-item (click)="confirmDelete(p)">
                <mat-icon>delete</mat-icon><span>Delete</span>
              </button>
            </mat-menu>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr
          mat-row
          *matRowDef="let row; columns: columns"
          class="clickable"
          [routerLink]="['/subscription-plans', row.id]"
        ></tr>
      </table>

      @if (!loading() && rows().length === 0) {
        <div class="empty">No subscription plans yet.</div>
      }
    </div>

    <mat-paginator
      [length]="total()"
      [pageSize]="size()"
      [pageIndex]="page() - 1"
      [pageSizeOptions]="[10, 20, 50]"
      (page)="onPage($event)"
    />
  `,
  styles: [
    `
      .page-header {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 1.5rem;
        gap: 1rem;
      }
      .page-header h1 {
        font: var(--mat-sys-headline-medium);
        margin: 0 0 0.25rem;
      }
      .page-header p {
        color: var(--mat-sys-on-surface-variant);
        margin: 0;
      }
      .filters {
        display: flex;
        gap: 1rem;
        align-items: center;
        margin-bottom: 1rem;
        flex-wrap: wrap;
      }
      .filters__search {
        flex: 1 1 260px;
      }
      .filters__status {
        width: 180px;
      }
      .table-wrap {
        background: var(--mat-sys-surface-container-low);
        border: 1px solid var(--mat-sys-outline-variant);
        border-radius: 12px;
        overflow: hidden;
      }
      table {
        width: 100%;
        background: transparent;
      }
      code {
        font-family: var(--mat-sys-typescale-body-medium-font, monospace);
        background: var(--mat-sys-surface-container);
        padding: 0.1rem 0.4rem;
        border-radius: 6px;
      }
      .clickable {
        cursor: pointer;
      }
      .empty {
        padding: 2rem;
        text-align: center;
        color: var(--mat-sys-on-surface-variant);
      }
      .status {
        text-transform: capitalize;
        padding: 0.15rem 0.6rem;
        border-radius: 999px;
        font: var(--mat-sys-label-small);
      }
      .status--active {
        background: var(--mat-sys-primary-container);
        color: var(--mat-sys-on-primary-container);
      }
      .status--inactive {
        background: var(--mat-sys-error-container);
        color: var(--mat-sys-on-error-container);
      }
    `,
  ],
})
export class PlanListComponent {
  private readonly api = inject(PlansService);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly columns = ['name', 'code', 'usage', 'status', 'actions'];
  readonly rows = signal<PlanListItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(20);
  readonly loading = signal(false);

  search = '';
  statusFilter: '' | 'active' | 'inactive' = '';

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    const isActive =
      this.statusFilter === '' ? undefined : this.statusFilter === 'active';
    this.api
      .list({
        page: this.page(),
        size: this.size(),
        search: this.search || undefined,
        isActive,
      })
      .subscribe({
        next: (res) => {
          this.rows.set(res.data);
          this.total.set(res.meta.total);
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
  }

  applyFilters(): void {
    this.page.set(1);
    this.load();
  }

  onPage(e: PageEvent): void {
    this.page.set(e.pageIndex + 1);
    this.size.set(e.pageSize);
    this.load();
  }

  activate(p: PlanListItem): void {
    this.api.activate(p.id).subscribe({
      next: () => {
        this.notify.success(`${p.name} activated.`);
        this.load();
      },
    });
  }

  deactivate(p: PlanListItem): void {
    this.api.deactivate(p.id).subscribe({
      next: () => {
        this.notify.success(`${p.name} deactivated.`);
        this.load();
      },
    });
  }

  confirmDelete(p: PlanListItem): void {
    const data: ConfirmDialogData = {
      title: 'Delete plan',
      message:
        p.usage_count > 0
          ? `"${p.name}" is assigned to ${p.usage_count} company(ies) and cannot `
            + `be deleted until they are reassigned.`
          : `Delete "${p.name}"? This cannot be undone from the UI.`,
      confirmText: 'Delete',
      destructive: true,
    };
    this.dialog
      .open(ConfirmDialogComponent, { data, width: '440px' })
      .afterClosed()
      .subscribe((confirmed) => {
        if (!confirmed) return;
        this.api.remove(p.id).subscribe({
          next: () => {
            this.notify.success(`${p.name} deleted.`);
            this.load();
          },
          // 422 (in-use) surfaces via the global error interceptor.
        });
      });
  }
}
