import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { DashboardApiService } from './dashboard.service';
import { CompanyDashboardOverview, DashboardOverview } from './dashboard.models';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [
    DatePipe,
    RouterLink,
    MatCardModule,
    MatButtonModule,
    MatIconModule,
    MatProgressBarModule,
  ],
  template: `
    @if (!auth.isEmailVerified() && auth.user()) {
      <div class="verify-banner">
        <mat-icon>mark_email_unread</mat-icon>
        <span class="verify-banner__text">
          Your email isn't verified yet. Check your inbox for the link.
        </span>
        <button mat-stroked-button (click)="resend()" [disabled]="resending()">
          Resend link
        </button>
      </div>
    }

    <header class="page-header">
      <h1>Welcome back{{ name() ? ', ' + name() : '' }}</h1>
      <p>{{ auth.isSuperAdmin() ? 'Platform overview.' : 'Your company at a glance.' }}</p>
    </header>

    @if (auth.isSuperAdmin()) {
      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }

      @if (error()) {
        <mat-card appearance="outlined" class="state-card">
          <mat-card-content>
            <mat-icon>error_outline</mat-icon>
            <p>Couldn't load the dashboard.</p>
            <button mat-stroked-button (click)="load()">Retry</button>
          </mat-card-content>
        </mat-card>
      }

      @if (data(); as d) {
        <!-- KPIs -->
        <section class="kpis">
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_companies }}</span>
            <span class="kpi__label">Total Companies</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.active_companies }}</span>
            <span class="kpi__label">Active</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.suspended_companies }}</span>
            <span class="kpi__label">Suspended</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_plans }}</span>
            <span class="kpi__label">Subscription Plans</span>
          </div>
        </section>

        <!-- Quick actions -->
        <section class="quick">
          <a mat-flat-button color="primary" routerLink="/companies/new">
            <mat-icon>add</mat-icon> Create Company
          </a>
          <a mat-stroked-button routerLink="/subscription-plans/new">
            <mat-icon>workspace_premium</mat-icon> Create Plan
          </a>
          <a mat-stroked-button routerLink="/audit-logs">
            <mat-icon>receipt_long</mat-icon> View Audit Logs
          </a>
          <a mat-stroked-button routerLink="/settings">
            <mat-icon>settings</mat-icon> Platform Settings
          </a>
        </section>

        <div class="grid">
          <!-- Recent companies -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Recent Companies</mat-card-title></mat-card-header>
            <mat-card-content>
              @if (d.recent_companies.length === 0) {
                <p class="empty">No companies yet.</p>
              } @else {
                <ul class="list">
                  @for (c of d.recent_companies; track c.id) {
                    <li>
                      <a [routerLink]="['/companies', c.id]">{{ c.name }}</a>
                      <span class="status status--{{ c.status }}">{{ c.status }}</span>
                      <span class="muted">{{ c.plan_name ?? 'No plan' }}</span>
                      <span class="muted date">{{ c.created_at | date: 'mediumDate' }}</span>
                    </li>
                  }
                </ul>
              }
            </mat-card-content>
          </mat-card>

          <!-- Recent activity -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Recent Activity</mat-card-title></mat-card-header>
            <mat-card-content>
              @if (d.recent_activity.length === 0) {
                <p class="empty">No activity recorded.</p>
              } @else {
                <ul class="list">
                  @for (a of d.recent_activity; track a.id) {
                    <li>
                      <span class="chip">{{ a.action }}</span>
                      <span>{{ a.entity_type }}</span>
                      <span class="muted">{{ a.actor_name ?? 'System' }}</span>
                      <span class="muted date">{{ a.created_at | date: 'short' }}</span>
                    </li>
                  }
                </ul>
              }
            </mat-card-content>
          </mat-card>

          <!-- Subscription overview -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Subscription Overview</mat-card-title></mat-card-header>
            <mat-card-content>
              @if (d.plan_distribution.length === 0) {
                <p class="empty">No plans configured.</p>
              } @else {
                <ul class="bars">
                  @for (p of d.plan_distribution; track p.plan_name) {
                    <li>
                      <div class="bars__row">
                        <span>{{ p.plan_name }}</span>
                        <span class="muted">{{ p.company_count }}</span>
                      </div>
                      <div class="bar">
                        <div class="bar__fill" [style.width.%]="pct(p.company_count)"></div>
                      </div>
                    </li>
                  }
                </ul>
              }
            </mat-card-content>
          </mat-card>

          <!-- Platform health -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Platform Health</mat-card-title></mat-card-header>
            <mat-card-content>
              <dl class="meta">
                <dt>Active companies</dt><dd>{{ d.kpis.active_companies }}</dd>
                <dt>Suspended companies</dt><dd>{{ d.kpis.suspended_companies }}</dd>
                <dt>Deactivated companies</dt><dd>{{ d.kpis.deactivated_companies }}</dd>
                <dt>Total companies</dt><dd>{{ d.kpis.total_companies }}</dd>
              </dl>
            </mat-card-content>
          </mat-card>
        </div>
      }
    } @else if (isCompanyWorkspace()) {
      @if (cLoading()) { <mat-progress-bar mode="indeterminate" /> }

      @if (cError()) {
        <mat-card appearance="outlined" class="state-card">
          <mat-card-content>
            <mat-icon>error_outline</mat-icon>
            <p>Couldn't load your dashboard.</p>
            <button mat-stroked-button (click)="loadCompany()">Retry</button>
          </mat-card-content>
        </mat-card>
      }

      @if (cData(); as d) {
        <!-- KPI cards -->
        <section class="kpis">
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_users }}</span>
            <span class="kpi__label">Total Users</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.active_users }}</span>
            <span class="kpi__label">Active Users</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_groups }}</span>
            <span class="kpi__label">Total Groups</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_api_keys }}</span>
            <span class="kpi__label">API Keys</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_contacts }}</span>
            <span class="kpi__label">Total Contacts</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_contact_lists }}</span>
            <span class="kpi__label">Contact Groups</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_sms_campaigns }}</span>
            <span class="kpi__label">Total Campaigns</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_sms_templates }}</span>
            <span class="kpi__label">SMS Templates</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.total_sms_messages }}</span>
            <span class="kpi__label">SMS Messages</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.messages_sent_today }}</span>
            <span class="kpi__label">Messages Sent Today</span>
          </div>
          <div class="kpi">
            <span class="kpi__value">{{ d.kpis.delivery_rate }}%</span>
            <span class="kpi__label">Delivery Rate</span>
          </div>
        </section>

        <!-- Quick actions -->
        <section class="quick">
          <a mat-flat-button color="primary" routerLink="/users">
            <mat-icon>person_add</mat-icon> Manage Users
          </a>
          <a mat-stroked-button routerLink="/company-settings">
            <mat-icon>business</mat-icon> Company Settings
          </a>
          <a mat-stroked-button routerLink="/sms">
            <mat-icon>sms</mat-icon> SMS Workspace
          </a>
        </section>

        <div class="grid">
          <!-- Company summary -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Company Summary</mat-card-title></mat-card-header>
            <mat-card-content>
              <dl class="meta">
                <dt>Company</dt><dd>{{ d.summary.company_name }}</dd>
                <dt>Plan</dt><dd>{{ d.summary.plan_name ?? 'No plan' }}</dd>
                <dt>Status</dt>
                <dd><span class="status status--{{ d.summary.plan_status }}">{{ d.summary.plan_status }}</span></dd>
                <dt>Users</dt>
                <dd>{{ d.summary.current_user_count }}{{ d.summary.user_limit !== null ? ' / ' + d.summary.user_limit : '' }}</dd>
              </dl>
              @if (d.summary.user_limit !== null) {
                <div class="bar">
                  <div class="bar__fill" [style.width.%]="usagePct(d.summary)"></div>
                </div>
              }
            </mat-card-content>
          </mat-card>

          <!-- Recently created users -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Recently Created Users</mat-card-title></mat-card-header>
            <mat-card-content>
              @if (d.recent_created_users.length === 0) {
                <p class="empty">No users yet.</p>
              } @else {
                <ul class="list">
                  @for (u of d.recent_created_users; track u.id) {
                    <li>
                      <a [routerLink]="['/users', u.id]">{{ u.full_name ?? u.email }}</a>
                      <span class="status status--{{ u.status }}">{{ u.status }}</span>
                      <span class="muted date">{{ u.created_at | date: 'mediumDate' }}</span>
                    </li>
                  }
                </ul>
              }
            </mat-card-content>
          </mat-card>

          <!-- Recently updated users -->
          <mat-card appearance="outlined">
            <mat-card-header><mat-card-title>Recently Updated Users</mat-card-title></mat-card-header>
            <mat-card-content>
              @if (d.recent_updated_users.length === 0) {
                <p class="empty">No users yet.</p>
              } @else {
                <ul class="list">
                  @for (u of d.recent_updated_users; track u.id) {
                    <li>
                      <a [routerLink]="['/users', u.id]">{{ u.full_name ?? u.email }}</a>
                      <span class="status status--{{ u.status }}">{{ u.status }}</span>
                      <span class="muted date">{{ u.updated_at | date: 'short' }}</span>
                    </li>
                  }
                </ul>
              }
            </mat-card-content>
          </mat-card>
        </div>
      }
    } @else {
      <mat-card appearance="outlined">
        <mat-card-content>
          <p>Your workspace modules will appear here.</p>
        </mat-card-content>
      </mat-card>
    }
  `,
  styles: [
    `
      .verify-banner {
        display: flex; align-items: center; gap: 0.75rem;
        padding: 0.75rem 1rem; margin-bottom: 1.5rem; border-radius: 10px;
        background: var(--mat-sys-tertiary-container);
        color: var(--mat-sys-on-tertiary-container);
      }
      .verify-banner__text { flex: 1; }
      .page-header { margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .kpis {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
        gap: 1rem; margin-bottom: 1.25rem;
      }
      .kpi {
        background: var(--mat-sys-surface-container-low);
        border: 1px solid var(--mat-sys-outline-variant);
        border-radius: 12px; padding: 1.25rem; display: flex; flex-direction: column;
      }
      .kpi__value { font: var(--mat-sys-display-small); }
      .kpi__label { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-label-large); }
      .quick { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1.5rem; }
      .grid {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
        gap: 1rem;
      }
      .list { list-style: none; margin: 0; padding: 0; }
      .list li {
        display: flex; align-items: center; gap: 0.75rem;
        padding: 0.5rem 0; border-bottom: 1px solid var(--mat-sys-outline-variant);
      }
      .list li:last-child { border-bottom: none; }
      .list a { color: var(--mat-sys-primary); text-decoration: none; font-weight: 500; }
      .muted { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .date { margin-left: auto; }
      .status, .chip {
        text-transform: capitalize; padding: 0.1rem 0.55rem;
        border-radius: 999px; font: var(--mat-sys-label-small);
      }
      .status--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .status--suspended, .status--deactivated {
        background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container);
      }
      .chip { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); }
      .bars { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.75rem; }
      .bars__row { display: flex; justify-content: space-between; margin-bottom: 0.25rem; }
      .bar { height: 8px; border-radius: 999px; background: var(--mat-sys-surface-container-high); overflow: hidden; }
      .bar__fill { height: 100%; background: var(--mat-sys-primary); }
      .meta { display: grid; grid-template-columns: 1fr auto; gap: 0.5rem 1rem; margin: 0; }
      .meta dt { color: var(--mat-sys-on-surface-variant); }
      .meta dd { margin: 0; text-align: right; }
      .empty { color: var(--mat-sys-on-surface-variant); padding: 0.5rem 0; }
      .state-card mat-card-content { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2rem; }
    `,
  ],
})
export class DashboardComponent {
  protected readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly api = inject(DashboardApiService);

  readonly resending = signal(false);
  readonly loading = signal(false);
  readonly error = signal(false);
  readonly data = signal<DashboardOverview | null>(null);

  // Company workspace dashboard state.
  readonly cLoading = signal(false);
  readonly cError = signal(false);
  readonly cData = signal<CompanyDashboardOverview | null>(null);

  // A company workspace = authenticated, not a super admin, has a company.
  readonly isCompanyWorkspace = computed(
    () => !this.auth.isSuperAdmin() && !!this.auth.user()?.company_id,
  );

  readonly name = computed(() => {
    const u = this.auth.user();
    return u ? [u.first_name, u.last_name].filter(Boolean).join(' ') : '';
  });

  readonly role = computed(() => this.auth.user()?.roles?.[0] ?? '');

  private maxCount = 1;

  constructor() {
    if (this.auth.isSuperAdmin()) {
      this.load();
    } else if (this.isCompanyWorkspace()) {
      this.loadCompany();
    }
  }

  loadCompany(): void {
    this.cLoading.set(true);
    this.cError.set(false);
    this.api.companyOverview().subscribe({
      next: (d) => {
        this.cData.set(d);
        this.cLoading.set(false);
      },
      error: () => {
        this.cError.set(true);
        this.cLoading.set(false);
      },
    });
  }

  usagePct(summary: { current_user_count: number; user_limit: number | null }): number {
    if (!summary.user_limit) return 0;
    return Math.min(100, Math.round((summary.current_user_count / summary.user_limit) * 100));
  }

  load(): void {
    this.loading.set(true);
    this.error.set(false);
    this.api.overview().subscribe({
      next: (d) => {
        this.maxCount = Math.max(
          1,
          ...d.plan_distribution.map((p) => p.company_count),
        );
        this.data.set(d);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  pct(count: number): number {
    return Math.round((count / this.maxCount) * 100);
  }

  resend(): void {
    if (this.resending()) return;
    this.resending.set(true);
    this.auth.resendVerification().subscribe({
      next: () => {
        this.notify.success('Verification email sent.');
        this.resending.set(false);
      },
      error: () => this.resending.set(false),
    });
  }
}
