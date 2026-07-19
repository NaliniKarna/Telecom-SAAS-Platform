import { Component, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

import { TelephonyService } from './telephony.service';
import { TelephonyConnection } from './telephony.models';
import { NotificationService } from '../../core/services/notification.service';

/**
 * Telephony (FreePBX / Asterisk) — platform PBX infrastructure, super admin only.
 *
 * Provider-managed model: the platform owns PBX configuration (hosts, AMI
 * credentials, the shared default connection). Company admins never see this;
 * they consume telecom features (voice, missed-call, campaigns) built on top.
 * Route + nav are gated to super admin, and the API rejects non-super-admins.
 */
@Component({
  selector: 'app-telephony',
  standalone: true,
  imports: [
    DatePipe,
    ReactiveFormsModule,
    MatCardModule,
    MatTableModule,
    MatButtonModule,
    MatIconModule,
    MatMenuModule,
    MatChipsModule,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    MatProgressBarModule,
    MatTooltipModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Telephony</h1>
        <p>
          The platform's FreePBX / Asterisk connection. AMI credentials stay internal
          to the platform and are managed by administrators only.
        </p>
      </div>
      @if (!formOpen() && connections().length === 0) {
        <button mat-flat-button color="primary" (click)="openCreate()">
          <mat-icon>add</mat-icon> Add connection
        </button>
      }
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    <!-- Create / edit form -->
    @if (formOpen()) {
      <mat-card class="tel-form">
        <h2>{{ editingId() ? 'Edit connection' : 'New connection' }}</h2>
        <form [formGroup]="form" (ngSubmit)="save()">
          <div class="grid">
            <mat-form-field appearance="outline">
              <mat-label>Name</mat-label>
              <input matInput formControlName="name" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Host</mat-label>
              <input matInput formControlName="host" placeholder="pbx.internal" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Port</mat-label>
              <input matInput type="number" formControlName="port" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>AMI username</mat-label>
              <input matInput formControlName="ami_username" autocomplete="off" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>AMI secret</mat-label>
              <input
                matInput
                type="password"
                formControlName="ami_secret"
                autocomplete="new-password"
                [placeholder]="editingId() ? 'Leave blank to keep current' : ''"
              />
            </mat-form-field>
            <mat-form-field appearance="outline" class="span-2">
              <mat-label>Description (optional)</mat-label>
              <input matInput formControlName="description" />
            </mat-form-field>
          </div>

          <div class="toggles">
            <mat-slide-toggle formControlName="use_tls">TLS</mat-slide-toggle>
            <mat-slide-toggle formControlName="enabled">Enabled</mat-slide-toggle>
          </div>

          <div class="actions">
            <button mat-button type="button" (click)="closeForm()">Cancel</button>
            <button
              mat-flat-button
              color="primary"
              type="submit"
              [disabled]="form.invalid || saving()"
            >
              {{ editingId() ? 'Save changes' : 'Create connection' }}
            </button>
          </div>
        </form>
      </mat-card>
    }

    <!-- Connections table -->
    @if (!loading() && connections().length === 0) {
      <mat-card class="empty">
        <mat-icon>settings_phone</mat-icon>
        <p>No PBX connections yet. Add one to connect the platform to Asterisk.</p>
      </mat-card>
    } @else if (connections().length) {
      <mat-card class="tel-table">
        <table mat-table [dataSource]="connections()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let c">
              <strong>{{ c.name }}</strong>
              @if (c.is_platform_default) {
                <span class="badge">default</span>
              }
              @if (c.description) {
                <div class="muted">{{ c.description }}</div>
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="endpoint">
            <th mat-header-cell *matHeaderCellDef>Endpoint</th>
            <td mat-cell *matCellDef="let c">
              {{ c.host }}:{{ c.port }}
              @if (c.use_tls) { <span class="chip-tls">TLS</span> }
              <div class="muted">AMI: {{ c.ami_username }}</div>
            </td>
          </ng-container>

          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let c">
              <span class="status status--{{ c.last_status }}">
                {{ c.last_status }}
              </span>
              @if (c.last_checked_at) {
                <div class="muted">{{ c.last_checked_at | date: 'short' }}</div>
              }
              @if (c.last_error) {
                <div class="muted err" [matTooltip]="c.last_error">
                  {{ c.last_error }}
                </div>
              }
            </td>
          </ng-container>

          <ng-container matColumnDef="enabled">
            <th mat-header-cell *matHeaderCellDef>Enabled</th>
            <td mat-cell *matCellDef="let c">
              <mat-icon [class.on]="c.enabled">
                {{ c.enabled ? 'check_circle' : 'cancel' }}
              </mat-icon>
            </td>
          </ng-container>

          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let c">
              <button
                mat-stroked-button
                (click)="test(c)"
                [disabled]="testingId() === c.id"
              >
                <mat-icon>network_check</mat-icon>
                {{ testingId() === c.id ? 'Testing…' : 'Test' }}
              </button>
              <button mat-icon-button [matMenuTriggerFor]="menu">
                <mat-icon>more_vert</mat-icon>
              </button>
              <mat-menu #menu>
                <button mat-menu-item (click)="openEdit(c)">
                  <mat-icon>edit</mat-icon> Edit
                </button>
                <button mat-menu-item (click)="remove(c)">
                  <mat-icon>delete</mat-icon> Delete
                </button>
              </mat-menu>
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns"></tr>
        </table>
      </mat-card>
    }
  `,
  styles: [
    `
      .page-header {
        display: flex;
        align-items: flex-start;
        justify-content: space-between;
        gap: 1rem;
        margin-bottom: 1rem;
      }
      .page-header h1 {
        margin: 0 0 0.25rem;
      }
      .page-header p {
        margin: 0;
        color: var(--mat-sys-on-surface-variant);
        max-width: 60ch;
      }
      .tel-form {
        padding: 1.25rem;
        margin-bottom: 1rem;
      }
      .tel-form h2 {
        margin: 0 0 1rem;
        font: var(--mat-sys-title-medium);
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 0.5rem 1rem;
      }
      .grid .span-2 {
        grid-column: 1 / -1;
      }
      .toggles {
        display: flex;
        gap: 1.5rem;
        margin: 0.5rem 0 1rem;
        flex-wrap: wrap;
      }
      .actions {
        display: flex;
        justify-content: flex-end;
        gap: 0.5rem;
      }
      .tel-table {
        padding: 0;
        overflow: auto;
      }
      table {
        width: 100%;
      }
      .badge {
        margin-left: 0.5rem;
        font-size: 0.7rem;
        font-weight: 600;
        text-transform: uppercase;
        padding: 0.1rem 0.4rem;
        border-radius: 6px;
        background: var(--mat-sys-primary-container);
        color: var(--mat-sys-on-primary-container);
      }
      .chip-tls {
        font-size: 0.7rem;
        padding: 0.05rem 0.35rem;
        border-radius: 5px;
        border: 1px solid var(--mat-sys-outline);
        margin-left: 0.35rem;
      }
      .muted {
        color: var(--mat-sys-on-surface-variant);
        font-size: 0.8rem;
      }
      .muted.err {
        color: var(--mat-sys-error);
        max-width: 22ch;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .status {
        text-transform: capitalize;
        font-weight: 600;
        font-size: 0.85rem;
      }
      .status--connected {
        color: #16a34a;
      }
      .status--error {
        color: var(--mat-sys-error);
      }
      .status--disconnected,
      .status--unknown {
        color: var(--mat-sys-on-surface-variant);
      }
      mat-icon.on {
        color: #16a34a;
      }
      .empty {
        text-align: center;
        padding: 2.5rem;
        color: var(--mat-sys-on-surface-variant);
      }
      .empty mat-icon {
        font-size: 40px;
        width: 40px;
        height: 40px;
        opacity: 0.6;
      }
      @media (max-width: 640px) {
        .grid {
          grid-template-columns: 1fr;
        }
      }
    `,
  ],
})
export class TelephonyComponent {
  private readonly api = inject(TelephonyService);
  private readonly notify = inject(NotificationService);
  private readonly fb = inject(FormBuilder);

  readonly columns = ['name', 'endpoint', 'status', 'enabled', 'actions'];

  readonly connections = signal<TelephonyConnection[]>([]);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly testingId = signal<string | null>(null);
  readonly editingId = signal<string | null>(null);
  readonly formOpen = signal(false);

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    description: [''],
    host: ['', [Validators.required]],
    port: [5038, [Validators.required, Validators.min(1), Validators.max(65535)]],
    ami_username: ['', [Validators.required]],
    ami_secret: [''],
    use_tls: [false],
    enabled: [true],
  });

  constructor() {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.api.listConnections().subscribe({
      next: (rows) => {
        this.connections.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  openCreate(): void {
    this.editingId.set(null);
    this.form.reset({
      name: '',
      description: '',
      host: '',
      port: 5038,
      ami_username: '',
      ami_secret: '',
      use_tls: false,
      enabled: true,
    });
    this.form.controls.ami_secret.addValidators(Validators.required);
    this.form.controls.ami_secret.updateValueAndValidity();
    this.formOpen.set(true);
  }

  openEdit(c: TelephonyConnection): void {
    this.editingId.set(c.id);
    this.form.reset({
      name: c.name,
      description: c.description ?? '',
      host: c.host,
      port: c.port,
      ami_username: c.ami_username,
      ami_secret: '', // blank = keep existing
      use_tls: c.use_tls,
      enabled: c.enabled,
    });
    // On edit the secret is optional (blank keeps current).
    this.form.controls.ami_secret.clearValidators();
    this.form.controls.ami_secret.updateValueAndValidity();
    this.formOpen.set(true);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
  }

  save(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    const v = this.form.getRawValue();
    const id = this.editingId();

    if (id) {
      // Update: omit ami_secret when left blank.
      const patch: Record<string, unknown> = {
        name: v.name,
        description: v.description || null,
        host: v.host,
        port: v.port,
        ami_username: v.ami_username,
        use_tls: v.use_tls,
        enabled: v.enabled,
      };
      if (v.ami_secret) patch['ami_secret'] = v.ami_secret;
      this.api.updateConnection(id, patch).subscribe({
        next: () => {
          this.notify.success('Connection updated.');
          this.saving.set(false);
          this.closeForm();
          this.load();
        },
        error: () => this.saving.set(false),
      });
    } else {
      this.api
        .createConnection({
          name: v.name,
          description: v.description || null,
          host: v.host,
          port: v.port,
          ami_username: v.ami_username,
          ami_secret: v.ami_secret,
          use_tls: v.use_tls,
          enabled: v.enabled,
        })
        .subscribe({
          next: () => {
            this.notify.success('Connection created.');
            this.saving.set(false);
            this.closeForm();
            this.load();
          },
          error: () => this.saving.set(false),
        });
    }
  }

  test(c: TelephonyConnection): void {
    this.testingId.set(c.id);
    this.api.testConnection(c.id).subscribe({
      next: (res) => {
        this.testingId.set(null);
        if (res.connected) {
          this.notify.success(
            `Connected (${res.provider}${res.latency_ms != null ? `, ${res.latency_ms} ms` : ''}).`,
          );
        } else {
          this.notify.error(`Not connected: ${res.detail}`);
        }
        this.load();
      },
      error: () => this.testingId.set(null),
    });
  }

  remove(c: TelephonyConnection): void {
    if (!confirm(`Delete connection "${c.name}"? This cannot be undone.`)) return;
    this.api.deleteConnection(c.id).subscribe({
      next: () => {
        this.notify.success('Connection deleted.');
        this.load();
      },
    });
  }
}
