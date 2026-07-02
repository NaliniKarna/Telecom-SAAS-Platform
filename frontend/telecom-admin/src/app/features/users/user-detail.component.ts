import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';

import { UsersService } from './users.service';
import { CompanyUser } from './user.models';
import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-user-detail',
  standalone: true,
  imports: [
    DatePipe, RouterLink, ReactiveFormsModule, MatCardModule,
    MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule,
    MatIconModule, MatProgressBarModule, MatDialogModule,
  ],
  template: `
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (user(); as u) {
      <header class="page-header">
        <div>
          <h1>{{ displayName(u) }}</h1>
          <span class="status status--{{ u.status }}">{{ u.status }}</span>
        </div>
        <div class="header-actions">
          @if (u.status === 'active' && !isSelf(u)) {
            <button mat-stroked-button (click)="deactivate(u)">
              <mat-icon>block</mat-icon> Deactivate
            </button>
          }
          @if (u.status !== 'active' && u.status !== 'pending') {
            <button mat-stroked-button (click)="activate(u)">
              <mat-icon>check_circle</mat-icon> Activate
            </button>
          }
          @if (!isSelf(u)) {
            <button mat-stroked-button color="warn" (click)="confirmDelete(u)">
              <mat-icon>delete</mat-icon> Delete
            </button>
          }
        </div>
      </header>

      <mat-card appearance="outlined">
        <mat-card-content>
          <form [formGroup]="form" (ngSubmit)="save()" class="form">
            <div class="row">
              <mat-form-field appearance="outline">
                <mat-label>First name</mat-label>
                <input matInput formControlName="first_name" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Last name</mat-label>
                <input matInput formControlName="last_name" />
              </mat-form-field>
            </div>
            <mat-form-field appearance="outline">
              <mat-label>Email</mat-label>
              <input matInput [value]="u.email" disabled />
              <mat-hint>Email can't be changed.</mat-hint>
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Role</mat-label>
              <mat-select formControlName="role">
                <mat-option value="company_user">Company User</mat-option>
                <mat-option value="company_admin">Company Admin</mat-option>
              </mat-select>
              @if (isSelf(u)) {
                <mat-hint>You can't change your own role.</mat-hint>
              }
            </mat-form-field>

            <dl class="meta">
              <dt>Email verified</dt><dd>{{ u.is_email_verified ? 'Yes' : 'No' }}</dd>
              <dt>Last login</dt><dd>{{ u.last_login_at ? (u.last_login_at | date: 'medium') : 'Never' }}</dd>
              <dt>Created</dt><dd>{{ u.created_at | date: 'medium' }}</dd>
            </dl>

            <div class="actions">
              <a mat-stroked-button routerLink="/users">Back</a>
              <button mat-flat-button color="primary" type="submit" [disabled]="saving()">
                Save changes
              </button>
            </div>
          </form>
        </mat-card-content>
      </mat-card>
    }
  `,
  styles: [
    `
      .page-header { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 1.5rem; gap: 1rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.5rem; }
      .header-actions { display: flex; gap: 0.5rem; flex-wrap: wrap; }
      .form { display: flex; flex-direction: column; gap: 0.5rem; max-width: 40rem; }
      .row { display: flex; gap: 0.75rem; }
      .row mat-form-field { flex: 1; }
      .meta { display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1.5rem; margin: 0.5rem 0 1rem; }
      .meta dt { color: var(--mat-sys-on-surface-variant); }
      .meta dd { margin: 0; }
      .actions { display: flex; gap: 0.75rem; }
      .status { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .status--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .status--pending { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
      .status--inactive, .status--locked { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    `,
  ],
})
export class UserDetailComponent {
  private readonly api = inject(UsersService);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);
  private readonly fb = inject(FormBuilder);

  readonly user = signal<CompanyUser | null>(null);
  readonly loading = signal(false);
  readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group({
    first_name: [''],
    last_name: [''],
    role: ['company_user'],
  });

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) this.load(id);
  }

  load(id: string): void {
    this.loading.set(true);
    this.api.get(id).subscribe({
      next: (u) => {
        this.user.set(u);
        this.form.patchValue({
          first_name: u.first_name ?? '',
          last_name: u.last_name ?? '',
          role: u.roles.includes('company_admin') ? 'company_admin' : 'company_user',
        });
        if (this.isSelf(u)) this.form.controls.role.disable();
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  isSelf(u: CompanyUser): boolean { return this.auth.user()?.id === u.id; }
  displayName(u: CompanyUser): string {
    return [u.first_name, u.last_name].filter(Boolean).join(' ') || u.email;
  }

  save(): void {
    const u = this.user();
    if (!u || this.saving()) return;
    this.saving.set(true);
    const v = this.form.getRawValue();
    this.api.update(u.id, {
      first_name: v.first_name || null,
      last_name: v.last_name || null,
      role: v.role as 'company_admin' | 'company_user',
    }).subscribe({
      next: (updated) => { this.user.set(updated); this.notify.success('User updated.'); this.saving.set(false); },
      error: () => this.saving.set(false),
    });
  }

  activate(u: CompanyUser): void {
    this.api.activate(u.id).subscribe({ next: (x) => { this.user.set(x); this.notify.success('User activated.'); } });
  }
  deactivate(u: CompanyUser): void {
    this.api.deactivate(u.id).subscribe({ next: (x) => { this.user.set(x); this.notify.success('User deactivated.'); } });
  }
  confirmDelete(u: CompanyUser): void {
    const data: ConfirmDialogData = {
      title: 'Delete user',
      message: `Delete ${this.displayName(u)} (${u.email})? This cannot be undone from the UI.`,
      confirmText: 'Delete', destructive: true,
    };
    this.dialog.open(ConfirmDialogComponent, { data, width: '440px' }).afterClosed().subscribe((ok) => {
      if (!ok) return;
      this.api.remove(u.id).subscribe({ next: () => { this.notify.success('User deleted.'); void this.router.navigate(['/users']); } });
    });
  }
}
