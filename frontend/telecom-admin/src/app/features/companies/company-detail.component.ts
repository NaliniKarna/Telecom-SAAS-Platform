import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';

import { CompaniesService } from './companies.service';
import { Company } from './company.models';
import { NotificationService } from '../../core/services/notification.service';
import { Permission } from '../../core/constants/rbac.constants';
import { HasPermissionDirective } from '../../shared/directives/has-permission.directive';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';
import { InviteAdminDialogComponent } from './invite-admin-dialog.component';

@Component({
  selector: 'app-company-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatDialogModule,
    HasPermissionDirective,
  ],
  template: `
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (company(); as c) {
      <header class="page-header">
        <div>
          <h1>{{ c.name }}</h1>
          <span class="status status--{{ c.status }}">{{ c.status }}</span>
        </div>
        <div class="header-actions">
          <a
            mat-stroked-button
            [routerLink]="['/companies', c.id, 'edit']"
            *appHasPermission="Permission.CompanyUpdate"
          >
            <mat-icon>edit</mat-icon><span>Edit</span>
          </a>
          <button mat-stroked-button (click)="inviteAdmin(c)"
            *appHasPermission="Permission.CompanyUpdate">
            <mat-icon>admin_panel_settings</mat-icon><span>Invite admin</span>
          </button>
          @if (c.status !== 'active') {
            <button mat-stroked-button (click)="activate(c)"
              *appHasPermission="Permission.CompanyActivate">
              <mat-icon>check_circle</mat-icon><span>Activate</span>
            </button>
          }
          @if (c.status === 'active') {
            <button mat-stroked-button (click)="suspend(c)"
              *appHasPermission="Permission.CompanyDeactivate">
              <mat-icon>pause_circle</mat-icon><span>Suspend</span>
            </button>
          }
          @if (c.status !== 'deactivated') {
            <button mat-stroked-button (click)="deactivate(c)"
              *appHasPermission="Permission.CompanyDeactivate">
              <mat-icon>block</mat-icon><span>Deactivate</span>
            </button>
          }
          <button mat-stroked-button color="warn" (click)="confirmDelete(c)"
            *appHasPermission="Permission.CompanyDelete">
            <mat-icon>delete</mat-icon><span>Delete</span>
          </button>
        </div>
      </header>

      <mat-card appearance="outlined">
        <mat-card-content>
          <dl class="meta">
            <dt>Slug</dt><dd>{{ c.slug }}</dd>
            <dt>Plan</dt><dd>{{ c.plan?.name ?? '—' }}</dd>
            <dt>Status</dt><dd class="cap">{{ c.status }}</dd>
            <dt>Contact email</dt><dd>{{ c.contact_email ?? '—' }}</dd>
            <dt>Contact phone</dt><dd>{{ c.contact_phone ?? '—' }}</dd>
            <dt>Max users</dt><dd>{{ c.max_users ?? 'Unlimited' }}</dd>
            <dt>API rate limit</dt>
            <dd>{{ c.api_rate_limit ? c.api_rate_limit + ' req/min' : 'Unlimited' }}</dd>
            <dt>Created</dt><dd>{{ c.created_at | date: 'medium' }}</dd>
            <dt>Updated</dt><dd>{{ c.updated_at | date: 'medium' }}</dd>
          </dl>

          <div class="entitlements">
            <span class="ent ent--{{ c.sms_enabled }}">SMS</span>
            <span class="ent ent--{{ c.voice_enabled }}">Voice</span>
            <span class="ent ent--{{ c.missed_call_enabled }}">Missed Call</span>
            <span class="ent ent--{{ c.freepbx_enabled }}">FreePBX</span>
          </div>
        </mat-card-content>
      </mat-card>

      <a routerLink="/companies" class="back">Back to companies</a>
    }
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
        margin: 0 0 0.5rem;
      }
      .header-actions {
        display: flex;
        gap: 0.5rem;
      }
      .meta {
        display: grid;
        grid-template-columns: auto 1fr;
        gap: 0.5rem 1.5rem;
        margin: 0;
      }
      .meta dt {
        color: var(--mat-sys-on-surface-variant);
      }
      .meta dd {
        margin: 0;
      }
      .cap {
        text-transform: capitalize;
      }
      .entitlements {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        margin-top: 1.25rem;
      }
      .ent {
        padding: 0.2rem 0.7rem;
        border-radius: 999px;
        font: var(--mat-sys-label-small);
        border: 1px solid var(--mat-sys-outline-variant);
        color: var(--mat-sys-on-surface-variant);
      }
      .ent--true {
        background: var(--mat-sys-primary-container);
        color: var(--mat-sys-on-primary-container);
        border-color: transparent;
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
      .status--suspended,
      .status--deactivated {
        background: var(--mat-sys-error-container);
        color: var(--mat-sys-on-error-container);
      }
      .back {
        display: inline-block;
        margin-top: 1.5rem;
        color: var(--mat-sys-primary);
        text-decoration: none;
      }
    `,
  ],
})
export class CompanyDetailComponent {
  private readonly api = inject(CompaniesService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);
  protected readonly Permission = Permission;

  readonly company = signal<Company | null>(null);
  readonly loading = signal(false);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) this.load(id);
  }

  load(id: string): void {
    this.loading.set(true);
    this.api.get(id).subscribe({
      next: (c) => {
        this.company.set(c);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  inviteAdmin(c: Company): void {
    this.dialog
      .open(InviteAdminDialogComponent, { width: '460px' })
      .afterClosed()
      .subscribe((payload) => {
        if (!payload) return;
        this.api.inviteAdmin(c.id, payload).subscribe({
          next: () =>
            this.notify.success(`Admin invite sent to ${payload.email}.`),
        });
      });
  }

  activate(c: Company): void {
    this.api.activate(c.id).subscribe({
      next: (updated) => {
        this.company.set(updated);
        this.notify.success('Company activated.');
      },
    });
  }

  deactivate(c: Company): void {
    this.api.deactivate(c.id).subscribe({
      next: (updated) => {
        this.company.set(updated);
        this.notify.success('Company deactivated.');
      },
    });
  }

  suspend(c: Company): void {
    this.api.suspend(c.id).subscribe({
      next: (updated) => {
        this.company.set(updated);
        this.notify.success('Company suspended.');
      },
    });
  }

  confirmDelete(c: Company): void {
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
            this.notify.success('Company deleted.');
            void this.router.navigate(['/companies']);
          },
        });
      });
  }
}