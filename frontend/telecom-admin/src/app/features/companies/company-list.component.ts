import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatTableModule } from '@angular/material/table';
import { MatPaginatorModule, PageEvent } from '@angular/material/paginator';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatMenuModule } from '@angular/material/menu';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';

import { CompaniesService } from './companies.service';
import { CompanyListItem, CompanyStatus } from './company.models';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { Permission } from '../../core/constants/rbac.constants';
import { HasPermissionDirective } from '../../shared/directives/has-permission.directive';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-company-list',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    FormsModule,
    MatTableModule,
    MatPaginatorModule,
    MatButtonModule,
    MatIconModule,
    MatChipsModule,
    MatProgressBarModule,
    MatMenuModule,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatDialogModule,
    HasPermissionDirective,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Companies</h1>
        <p>Manage tenant companies on the platform.</p>
      </div>
      <button
        mat-flat-button
        color="primary"
        routerLink="/companies/new"
        *appHasPermission="Permission.CompanyCreate"
      >
        <mat-icon>add</mat-icon>
        New company
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
          placeholder="Name or slug"
        />
        <mat-icon matSuffix>search</mat-icon>
      </mat-form-field>

      <mat-form-field appearance="outline" class="filters__status">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="applyFilters()">
          <mat-option [value]="''">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="deactivated">Deactivated</mat-option>
          <mat-option value="suspended">Suspended</mat-option>
        </mat-select>
      </mat-form-field>

      <button mat-stroked-button (click)="applyFilters()">Apply</button>
    </div>

    <div class="table-wrap">
      <table mat-table [dataSource]="rows()">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Name</th>
          <td mat-cell *matCellDef="let c">{{ c.name }}</td>
        </ng-container>
        <ng-container matColumnDef="slug">
          <th mat-header-cell *matHeaderCellDef>Slug</th>
          <td mat-cell *matCellDef="let c">{{ c.slug }}</td>
        </ng-container>
        <ng-container matColumnDef="plan">
          <th mat-header-cell *matHeaderCellDef>Plan</th>
          <td mat-cell *matCellDef="let c">{{ c.plan?.name || '—' }}</td>
        </ng-container>
        <ng-container matColumnDef="contact_email">
          <th mat-header-cell *matHeaderCellDef>Contact Email</th>
          <td mat-cell *matCellDef="let c">
            @if (c.contact_email) {
              <a
                [href]="'mailto:' + c.contact_email"
                (click)="$event.stopPropagation()"
                >{{ c.contact_email }}</a
              >
            } @else {
              <span class="muted">—</span>
            }
          </td>
        </ng-container>
        <ng-container matColumnDef="contact_phone">
          <th mat-header-cell *matHeaderCellDef>Contact Phone</th>
          <td mat-cell *matCellDef="let c">{{ c.contact_phone || '—' }}</td>
        </ng-container>
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef>Status</th>
          <td mat-cell *matCellDef="let c">
            <span class="status status--{{ c.status }}">{{ c.status }}</span>
          </td>
        </ng-container>
        <ng-container matColumnDef="created_at">
          <th mat-header-cell *matHeaderCellDef>Created</th>
          <td mat-cell *matCellDef="let c">{{ c.created_at | date: 'mediumDate' }}</td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let c">
            <button mat-icon-button [matMenuTriggerFor]="menu" (click)="$event.stopPropagation()">
              <mat-icon>more_vert</mat-icon>
            </button>
            <mat-menu #menu="matMenu">
              <button mat-menu-item [routerLink]="['/companies', c.id]">
                <mat-icon>visibility</mat-icon><span>View</span>
              </button>
              @if (c.status !== 'active') {
                <button mat-menu-item (click)="activate(c)"
                  *appHasPermission="Permission.CompanyActivate">
                  <mat-icon>check_circle</mat-icon><span>Activate</span>
                </button>
              }
              @if (c.status === 'active') {
                <button mat-menu-item (click)="suspend(c)"
                  *appHasPermission="Permission.CompanyDeactivate">
                  <mat-icon>pause_circle</mat-icon><span>Suspend</span>
                </button>
              }
              @if (c.status !== 'deactivated') {
                <button mat-menu-item (click)="deactivate(c)"
                  *appHasPermission="Permission.CompanyDeactivate">
                  <mat-icon>block</mat-icon><span>Deactivate</span>
                </button>
              }
              <button mat-menu-item (click)="confirmDelete(c)"
                *appHasPermission="Permission.CompanyDelete"
                class="danger-item">
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
          [routerLink]="['/companies', row.id]"
        ></tr>
      </table>

      @if (!loading() && rows().length === 0) {
        <div class="empty">No companies yet.</div>
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
      .muted {
        color: var(--mat-sys-on-surface-variant);
      }
      td a {
        color: var(--mat-sys-primary);
        text-decoration: none;
      }
      td a:hover {
        text-decoration: underline;
      }
      .status--active {
        background: var(--mat-sys-primary-container);
        color: var(--mat-sys-on-primary-container);
      }
      .status--suspended,
      .status--deactivated {
        background: var(--mat-sys-error-container);
        color: var(--mat-sys-on-error-container);
      }
    `,
  ],
})
export class CompanyListComponent {
  private readonly api = inject(CompaniesService);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);
  protected readonly auth = inject(AuthService);
  protected readonly Permission = Permission;

  readonly columns = [
    'name',
    'slug',
    'plan',
    'contact_email',
    'contact_phone',
    'status',
    'created_at',
    'actions',
  ];
  readonly rows = signal<CompanyListItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(20);
  readonly loading = signal(false);

  // Filter state (two-way bound in the toolbar).
  search = '';
  statusFilter: CompanyStatus | '' = '';

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api
      .list({
        page: this.page(),
        size: this.size(),
        search: this.search || undefined,
        status: this.statusFilter || undefined,
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
    this.page.set(1); // reset to first page when filters change
    this.load();
  }

  onPage(e: PageEvent): void {
    this.page.set(e.pageIndex + 1);
    this.size.set(e.pageSize);
    this.load();
  }

  activate(c: CompanyListItem): void {
    this.api.activate(c.id).subscribe({
      next: () => {
        this.notify.success(`${c.name} activated.`);
        this.load();
      },
    });
  }

  deactivate(c: CompanyListItem): void {
    this.api.deactivate(c.id).subscribe({
      next: () => {
        this.notify.success(`${c.name} deactivated.`);
        this.load();
      },
    });
  }

  suspend(c: CompanyListItem): void {
    this.api.suspend(c.id).subscribe({
      next: () => {
        this.notify.success(`${c.name} suspended.`);
        this.load();
      },
    });
  }

  confirmDelete(c: CompanyListItem): void {
    const data: ConfirmDialogData = {
      title: 'Delete company',
      message: `Delete "${c.name}"? This removes it from the platform. `
        + `This action cannot be undone from the UI.`,
      confirmText: 'Delete',
      destructive: true,
    };
    this.dialog
      .open(ConfirmDialogComponent, { data, width: '420px' })
      .afterClosed()
      .subscribe((confirmed) => {
        if (!confirmed) return;
        this.api.remove(c.id).subscribe({
          next: () => {
            this.notify.success(`${c.name} deleted.`);
            this.load();
          },
        });
      });
  }
}