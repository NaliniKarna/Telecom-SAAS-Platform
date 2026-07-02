import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatChipsModule } from '@angular/material/chips';

import { CompanySettingsService } from './company-settings.service';
import { CompanySettings, PendingChangeRequest } from './company-settings.models';
import { NotificationService } from '../../core/services/notification.service';

// A small, common subset; the input is free-text-capable via the select's
// typeahead is out of scope — a fixed list keeps it simple and valid.
const TIMEZONES = [
  'UTC', 'America/New_York', 'America/Chicago', 'America/Denver',
  'America/Los_Angeles', 'Europe/London', 'Europe/Paris', 'Europe/Berlin',
  'Asia/Dubai', 'Asia/Kolkata', 'Asia/Kathmandu', 'Asia/Singapore',
  'Asia/Tokyo', 'Australia/Sydney',
];

@Component({
  selector: 'app-company-settings',
  standalone: true,
  imports: [
    DatePipe, ReactiveFormsModule, MatCardModule, MatFormFieldModule,
    MatInputModule, MatSelectModule, MatButtonModule, MatIconModule,
    MatProgressBarModule, MatChipsModule,
  ],
  template: `
    <header class="page-header">
      <h1>Company Settings</h1>
      <p>Manage your company profile and branding.</p>
    </header>

    @if (pending(); as pr) {
      <div class="pending-banner">
        <mat-icon>hourglass_top</mat-icon>
        <div class="pending-banner__text">
          <strong>Changes pending approval</strong>
          <span>
            @for (f of pendingFields(pr); track f) {
              {{ label(f) }}: <em>{{ pr.changes[f].new ?? '—' }}</em>{{ !$last ? ', ' : '' }}
            }
          </span>
          <span class="muted">A super admin must approve these before they take effect.</span>
        </div>
      </div>
    }

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (error()) {
      <mat-card appearance="outlined" class="state-card">
        <mat-card-content>
          <mat-icon>error_outline</mat-icon>
          <p>Couldn't load company settings.</p>
          <button mat-stroked-button (click)="load()">Retry</button>
        </mat-card-content>
      </mat-card>
    }

    @if (data(); as c) {
      <div class="grid">
        <!-- Editable profile -->
        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Profile</mat-card-title></mat-card-header>
          <mat-card-content>
            <form [formGroup]="form" (ngSubmit)="save()" class="form">
              <mat-form-field appearance="outline">
                <mat-label>Company name</mat-label>
                <input matInput formControlName="name" />
                @if (form.controls.name.hasError('required')) {
                  <mat-error>Company name is required.</mat-error>
                }
              </mat-form-field>
              <div class="row">
                <mat-form-field appearance="outline">
                  <mat-label>Contact email</mat-label>
                  <input matInput type="email" formControlName="contact_email" />
                  @if (form.controls.contact_email.hasError('email')) {
                    <mat-error>Enter a valid email.</mat-error>
                  }
                </mat-form-field>
                <mat-form-field appearance="outline">
                  <mat-label>Contact phone</mat-label>
                  <input matInput formControlName="contact_phone" />
                </mat-form-field>
              </div>
              <mat-form-field appearance="outline">
                <mat-label>Address</mat-label>
                <textarea matInput rows="2" formControlName="address"></textarea>
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Timezone</mat-label>
                <mat-select formControlName="timezone">
                  <mat-option [value]="null">Not set</mat-option>
                  @for (tz of timezones; track tz) {
                    <mat-option [value]="tz">{{ tz }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              <div class="actions">
                <button mat-flat-button color="primary" type="submit" [disabled]="saving() || form.invalid">
                  Save changes
                </button>
              </div>
            </form>
          </mat-card-content>
        </mat-card>

        <!-- Logo -->
        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Company Logo</mat-card-title></mat-card-header>
          <mat-card-content class="logo">
            <div class="logo__preview">
              @if (c.logo_url) {
                <img [src]="c.logo_url" alt="Company logo" />
              } @else {
                <mat-icon>image</mat-icon>
              }
            </div>
            <input #fileInput type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" hidden (change)="onFile($event)" />
            <button mat-stroked-button (click)="fileInput.click()" [disabled]="uploading()">
              <mat-icon>upload</mat-icon> {{ uploading() ? 'Uploading…' : 'Upload logo' }}
            </button>
            <p class="logo__hint">PNG, JPEG, WebP or SVG. Max 2 MB.</p>
          </mat-card-content>
        </mat-card>

        <!-- Read-only plan/limits/features -->
        <mat-card appearance="outlined" class="readonly">
          <mat-card-header>
            <mat-card-title>Subscription &amp; Limits</mat-card-title>
            <mat-card-subtitle>Managed by the platform administrator</mat-card-subtitle>
          </mat-card-header>
          <mat-card-content>
            <dl class="meta">
              <dt>Plan</dt><dd>{{ c.plan?.name ?? 'No plan' }}</dd>
              <dt>Status</dt><dd><span class="status status--{{ c.status }}">{{ c.status }}</span></dd>
              <dt>User limit</dt><dd>{{ c.max_users ?? 'Unlimited' }}</dd>
              <dt>API rate limit</dt><dd>{{ c.api_rate_limit ?? 'Unlimited' }}</dd>
              <dt>Created</dt><dd>{{ c.created_at | date: 'mediumDate' }}</dd>
            </dl>
            <div class="features">
              <span class="features__label">Enabled features</span>
              <mat-chip-set>
                @if (c.sms_enabled) { <mat-chip>SMS</mat-chip> }
                @if (c.voice_enabled) { <mat-chip>Voice</mat-chip> }
                @if (c.missed_call_enabled) { <mat-chip>Missed Call</mat-chip> }
                @if (c.freepbx_enabled) { <mat-chip>FreePBX</mat-chip> }
                @if (!c.sms_enabled && !c.voice_enabled && !c.missed_call_enabled && !c.freepbx_enabled) {
                  <span class="muted">None enabled</span>
                }
              </mat-chip-set>
            </div>
          </mat-card-content>
        </mat-card>
      </div>
    }
  `,
  styles: [
    `
      .page-header { margin-bottom: 1.5rem; }
      .pending-banner {
        display: flex; align-items: flex-start; gap: 0.75rem;
        padding: 0.85rem 1rem; margin-bottom: 1.5rem; border-radius: 10px;
        background: var(--mat-sys-tertiary-container);
        color: var(--mat-sys-on-tertiary-container);
      }
      .pending-banner__text { display: flex; flex-direction: column; gap: 0.1rem; }
      .pending-banner em { font-style: normal; font-weight: 600; }
      .pending-banner .muted { opacity: 0.8; font: var(--mat-sys-body-small); }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; align-items: start; }
      .form { display: flex; flex-direction: column; gap: 0.5rem; }
      .row { display: flex; gap: 0.75rem; }
      .row mat-form-field { flex: 1; }
      .actions { margin-top: 0.5rem; }
      .logo { display: flex; flex-direction: column; align-items: flex-start; gap: 0.75rem; }
      .logo__preview {
        width: 120px; height: 120px; border-radius: 12px;
        border: 1px solid var(--mat-sys-outline-variant);
        display: flex; align-items: center; justify-content: center; overflow: hidden;
        background: var(--mat-sys-surface-container);
      }
      .logo__preview img { width: 100%; height: 100%; object-fit: contain; }
      .logo__preview mat-icon { font-size: 3rem; width: 3rem; height: 3rem; opacity: 0.4; }
      .logo__hint { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); margin: 0; }
      .readonly { background: var(--mat-sys-surface-container-low); }
      .meta { display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1.5rem; margin: 0 0 1rem; }
      .meta dt { color: var(--mat-sys-on-surface-variant); }
      .meta dd { margin: 0; text-align: right; }
      .features__label { display: block; color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-label-small); margin-bottom: 0.5rem; }
      .muted { color: var(--mat-sys-on-surface-variant); }
      .status { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .status--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .status--suspended, .status--deactivated { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
      .state-card mat-card-content { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2rem; }
    `,
  ],
})
export class CompanySettingsComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(CompanySettingsService);
  private readonly notify = inject(NotificationService);

  readonly timezones = TIMEZONES;
  readonly data = signal<CompanySettings | null>(null);
  readonly pending = signal<PendingChangeRequest | null>(null);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly uploading = signal(false);
  readonly error = signal(false);

  private readonly fieldLabels: Record<string, string> = {
    name: 'Company name',
    contact_email: 'Contact email',
    contact_phone: 'Contact phone',
  };

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    contact_email: this.fb.control<string | null>(null, [Validators.email]),
    contact_phone: this.fb.control<string | null>(null),
    address: this.fb.control<string | null>(null),
    timezone: this.fb.control<string | null>(null),
  });

  constructor() { this.load(); this.loadPending(); }

  label(f: string): string { return this.fieldLabels[f] ?? f; }
  pendingFields(pr: PendingChangeRequest): string[] { return Object.keys(pr.changes); }

  loadPending(): void {
    this.api.pending().subscribe({
      next: (pr) => this.pending.set(pr),
      error: () => this.pending.set(null),
    });
  }

  load(): void {
    this.loading.set(true);
    this.error.set(false);
    this.api.get().subscribe({
      next: (c) => {
        this.data.set(c);
        this.form.patchValue({
          name: c.name,
          contact_email: c.contact_email,
          contact_phone: c.contact_phone,
          address: c.address,
          timezone: c.timezone,
        });
        this.loading.set(false);
      },
      error: () => { this.error.set(true); this.loading.set(false); },
    });
  }

  save(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    this.api.update(this.form.getRawValue()).subscribe({
      next: (result) => {
        this.saving.set(false);
        if (result.pending_request) {
          this.pending.set(result.pending_request);
          this.notify.success('Some changes were submitted for super-admin approval.');
        }
        if (result.immediate_applied.length > 0) {
          this.notify.success('Settings saved.');
        }
        // Refresh the live values (immediate fields may have changed).
        this.load();
      },
      error: () => this.saving.set(false),
    });
  }

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.uploading.set(true);
    this.api.uploadLogo(file).subscribe({
      next: (c) => { this.data.set(c); this.notify.success('Logo updated.'); this.uploading.set(false); input.value = ''; },
      error: () => { this.uploading.set(false); input.value = ''; },
    });
  }
}
