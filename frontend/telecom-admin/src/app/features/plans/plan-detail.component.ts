import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog, MatDialogModule } from '@angular/material/dialog';

import { PlansService } from './plans.service';
import { SubscriptionPlan } from './plan.models';
import { NotificationService } from '../../core/services/notification.service';
import {
  ConfirmDialogComponent,
  ConfirmDialogData,
} from '../../shared/components/confirm-dialog.component';

@Component({
  selector: 'app-plan-detail',
  standalone: true,
  imports: [
    RouterLink,
    DatePipe,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
    MatDialogModule,
  ],
  template: `
    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (plan(); as p) {
      <header class="page-header">
        <div>
          <h1>{{ p.name }}</h1>
          <span class="status status--{{ p.is_active ? 'active' : 'inactive' }}">
            {{ p.is_active ? 'active' : 'inactive' }}
          </span>
        </div>
        <div class="header-actions">
          <a mat-stroked-button [routerLink]="['/subscription-plans', p.id, 'edit']">
            <mat-icon>edit</mat-icon> Edit
          </a>
          @if (p.is_active) {
            <button mat-stroked-button (click)="deactivate(p)">
              <mat-icon>block</mat-icon> Deactivate
            </button>
          } @else {
            <button mat-stroked-button (click)="activate(p)">
              <mat-icon>check_circle</mat-icon> Activate
            </button>
          }
          <button mat-stroked-button color="warn" (click)="confirmDelete(p)">
            <mat-icon>delete</mat-icon> Delete
          </button>
        </div>
      </header>

      <mat-card appearance="outlined">
        <mat-card-content>
          <h2>General</h2>
          <dl class="meta">
            <dt>Code</dt><dd><code>{{ p.code }}</code></dd>
            <dt>Description</dt><dd>{{ p.description ?? '—' }}</dd>
            <dt>Companies using this plan</dt><dd>{{ usage() }}</dd>
            <dt>Status</dt><dd class="cap">{{ p.is_active ? 'active' : 'inactive' }}</dd>
          </dl>

          <h2>Limits</h2>
          <dl class="meta">
            <dt>Max users</dt><dd>{{ p.default_max_users ?? 'Unlimited' }}</dd>
            <dt>Max API keys</dt><dd>{{ p.default_max_api_keys ?? 'Unlimited' }}</dd>
            <dt>API rate limit</dt>
            <dd>{{ p.default_api_rate_limit ? p.default_api_rate_limit + ' req/min' : 'Unlimited' }}</dd>
            <dt>Monthly SMS limit</dt><dd>{{ p.default_monthly_sms_limit ?? 'Unlimited' }}</dd>
            <dt>Monthly voice minutes</dt><dd>{{ p.default_monthly_voice_minutes ?? 'Unlimited' }}</dd>
          </dl>

          <h2>Features</h2>
          <div class="entitlements">
            <span class="ent ent--{{ p.default_sms_enabled }}">SMS</span>
            <span class="ent ent--{{ p.default_voice_enabled }}">Voice</span>
            <span class="ent ent--{{ p.default_missed_call_enabled }}">Missed Call</span>
            <span class="ent ent--{{ p.default_freepbx_enabled }}">FreePBX</span>
            <span class="ent ent--{{ p.default_api_access_enabled }}">API Access</span>
          </div>

          <h2>Audit</h2>
          <dl class="meta">
            <dt>Created</dt><dd>{{ p.created_at | date: 'medium' }}</dd>
            <dt>Updated</dt><dd>{{ p.updated_at | date: 'medium' }}</dd>
          </dl>
        </mat-card-content>
      </mat-card>

      <a routerLink="/subscription-plans" class="back">← Back to plans</a>
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
        flex-wrap: wrap;
      }
      h2 {
        font: var(--mat-sys-title-small);
        color: var(--mat-sys-on-surface-variant);
        margin: 1.5rem 0 0.5rem;
      }
      h2:first-child {
        margin-top: 0;
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
      code {
        background: var(--mat-sys-surface-container);
        padding: 0.1rem 0.4rem;
        border-radius: 6px;
      }
      .cap {
        text-transform: capitalize;
      }
      .entitlements {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
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
      .status--inactive {
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
export class PlanDetailComponent {
  private readonly api = inject(PlansService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);

  readonly plan = signal<SubscriptionPlan | null>(null);
  readonly usage = signal(0);
  readonly loading = signal(false);

  constructor() {
    const id = this.route.snapshot.paramMap.get('id');
    if (id) this.load(id);
  }

  load(id: string): void {
    this.loading.set(true);
    this.api.get(id).subscribe({
      next: (res) => {
        this.plan.set(res.data);
        this.usage.set(res.usage_count);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  activate(p: SubscriptionPlan): void {
    this.api.activate(p.id).subscribe({
      next: (updated) => {
        this.plan.set(updated);
        this.notify.success('Plan activated.');
      },
    });
  }

  deactivate(p: SubscriptionPlan): void {
    this.api.deactivate(p.id).subscribe({
      next: (updated) => {
        this.plan.set(updated);
        this.notify.success('Plan deactivated.');
      },
    });
  }

  confirmDelete(p: SubscriptionPlan): void {
    const data: ConfirmDialogData = {
      title: 'Delete plan',
      message:
        this.usage() > 0
          ? `"${p.name}" is assigned to ${this.usage()} company(ies) and cannot `
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
            this.notify.success('Plan deleted.');
            void this.router.navigate(['/subscription-plans']);
          },
        });
      });
  }
}
