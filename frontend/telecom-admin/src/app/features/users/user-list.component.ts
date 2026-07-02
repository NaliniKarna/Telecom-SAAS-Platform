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

import { UsersService } from './users.service';
import { UserListItem, UserStatus } from './user.models';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';
import { UserInviteDialogComponent } from './user-invite-dialog.component';

@Component({
  selector: 'app-user-list',
  standalone: true,
  imports: [
    RouterLink, FormsModule, MatTableModule, MatPaginatorModule,
    MatButtonModule, MatIconModule, MatProgressBarModule, MatMenuModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatDialogModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Users</h1>
        <p>Manage the people in your company.</p>
      </div>
      <button mat-flat-button color="primary" (click)="openInvite()">
        <mat-icon>person_add</mat-icon> Invite user
      </button>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    <div class="filters">
      <mat-form-field appearance="outline" class="f-search">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="apply()"
          placeholder="Name or email" />
        <mat-icon matSuffix>search</mat-icon>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="statusFilter" (selectionChange)="apply()">
          <mat-option [value]="''">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="pending">Pending</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
          <mat-option value="locked">Locked</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Role</mat-label>
        <mat-select [(ngModel)]="roleFilter" (selectionChange)="apply()">
          <mat-option [value]="''">All</mat-option>
          <mat-option value="company_admin">Company Admin</mat-option>
          <mat-option value="company_user">Company User</mat-option>
        </mat-select>
      </mat-form-field>
      <button mat-stroked-button (click)="reset()">Clear</button>
    </div>

    <div class="table-wrap">
      <table mat-table [dataSource]="rows()">
        <ng-container matColumnDef="name">
          <th mat-header-cell *matHeaderCellDef>Name</th>
          <td mat-cell *matCellDef="let u">{{ displayName(u) }}</td>
        </ng-container>
        <ng-container matColumnDef="email">
          <th mat-header-cell *matHeaderCellDef>Email</th>
          <td mat-cell *matCellDef="let u">{{ u.email }}</td>
        </ng-container>
        <ng-container matColumnDef="role">
          <th mat-header-cell *matHeaderCellDef>Role</th>
          <td mat-cell *matCellDef="let u">{{ roleLabel(u.roles) }}</td>
        </ng-container>
        <ng-container matColumnDef="status">
          <th mat-header-cell *matHeaderCellDef>Status</th>
          <td mat-cell *matCellDef="let u">
            <span class="status status--{{ u.status }}">{{ u.status }}</span>
          </td>
        </ng-container>
        <ng-container matColumnDef="actions">
          <th mat-header-cell *matHeaderCellDef></th>
          <td mat-cell *matCellDef="let u">
            <button mat-icon-button [matMenuTriggerFor]="menu" (click)="$event.stopPropagation()">
              <mat-icon>more_vert</mat-icon>
            </button>
            <mat-menu #menu="matMenu">
              <button mat-menu-item [routerLink]="['/users', u.id]">
                <mat-icon>edit</mat-icon><span>View / Edit</span>
              </button>
              @if (u.status === 'active' && !isSelf(u)) {
                <button mat-menu-item (click)="deactivate(u)">
                  <mat-icon>block</mat-icon><span>Deactivate</span>
                </button>
              }
              @if (u.status !== 'active' && u.status !== 'pending') {
                <button mat-menu-item (click)="activate(u)">
                  <mat-icon>check_circle</mat-icon><span>Activate</span>
                </button>
              }
              @if (!isSelf(u)) {
                <button mat-menu-item (click)="confirmDelete(u)">
                  <mat-icon>delete</mat-icon><span>Delete</span>
                </button>
              }
            </mat-menu>
          </td>
        </ng-container>

        <tr mat-header-row *matHeaderRowDef="columns"></tr>
        <tr mat-row *matRowDef="let row; columns: columns" class="clickable"
          [routerLink]="['/users', row.id]"></tr>
      </table>

      @if (!loading() && rows().length === 0) {
        <div class="empty">No users match these filters.</div>
      }
    </div>

    <mat-paginator [length]="total()" [pageSize]="size()" [pageIndex]="page() - 1"
      [pageSizeOptions]="[10, 20, 50]" (page)="onPage($event)" />
  `,
  styles: [
    `
      .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; gap: 1rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .filters { display: flex; gap: 0.75rem; align-items: center; margin-bottom: 1rem; flex-wrap: wrap; }
      .f-search { flex: 1 1 240px; }
      .table-wrap { background: var(--mat-sys-surface-container-low); border: 1px solid var(--mat-sys-outline-variant); border-radius: 12px; overflow: hidden; }
      table { width: 100%; background: transparent; }
      .clickable { cursor: pointer; }
      .empty { padding: 2rem; text-align: center; color: var(--mat-sys-on-surface-variant); }
      .status { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .status--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .status--pending { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
      .status--inactive, .status--locked { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    `,
  ],
})
export class UserListComponent {
  private readonly api = inject(UsersService);
  private readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly columns = ['name', 'email', 'role', 'status', 'actions'];
  readonly rows = signal<UserListItem[]>([]);
  readonly total = signal(0);
  readonly page = signal(1);
  readonly size = signal(20);
  readonly loading = signal(false);

  search = '';
  statusFilter: '' | UserStatus = '';
  roleFilter = '';

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.list({
      page: this.page(), size: this.size(),
      search: this.search || undefined,
      status: this.statusFilter || undefined,
      role: this.roleFilter || undefined,
    }).subscribe({
      next: (res) => { this.rows.set(res.data); this.total.set(res.meta.total); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  apply(): void { this.page.set(1); this.load(); }
  reset(): void { this.search = ''; this.statusFilter = ''; this.roleFilter = ''; this.page.set(1); this.load(); }
  onPage(e: PageEvent): void { this.page.set(e.pageIndex + 1); this.size.set(e.pageSize); this.load(); }

  isSelf(u: UserListItem): boolean { return this.auth.user()?.id === u.id; }
  displayName(u: UserListItem): string {
    return [u.first_name, u.last_name].filter(Boolean).join(' ') || '—';
  }
  roleLabel(roles: string[]): string {
    if (roles.includes('company_admin')) return 'Company Admin';
    if (roles.includes('company_user')) return 'Company User';
    return roles.join(', ') || '—';
  }

  openInvite(): void {
    this.dialog.open(UserInviteDialogComponent).afterClosed().subscribe((payload) => {
      if (!payload) return;
      this.api.invite(payload).subscribe({
        next: () => { this.notify.success(`Invite sent to ${payload.email}.`); this.load(); },
      });
    });
  }

  activate(u: UserListItem): void {
    this.api.activate(u.id).subscribe({ next: () => { this.notify.success('User activated.'); this.load(); } });
  }
  deactivate(u: UserListItem): void {
    this.api.deactivate(u.id).subscribe({ next: () => { this.notify.success('User deactivated.'); this.load(); } });
  }
  confirmDelete(u: UserListItem): void {
    const data: ConfirmDialogData = {
      title: 'Delete user',
      message: `Delete ${this.displayName(u)} (${u.email})? This cannot be undone from the UI.`,
      confirmText: 'Delete', destructive: true,
    };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.api.remove(u.id).subscribe({ next: () => { this.notify.success('User deleted.'); this.load(); } });
    });
  }
}
