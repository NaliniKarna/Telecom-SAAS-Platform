import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { SettingsService } from './settings.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-platform-settings',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    MatButtonModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <h1>Platform Settings</h1>
      <p>Global configuration for the platform.</p>
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (error()) {
      <mat-card appearance="outlined" class="state-card">
        <mat-card-content>
          <p>Couldn't load settings.</p>
          <button mat-stroked-button (click)="load()">Retry</button>
        </mat-card-content>
      </mat-card>
    }

    @if (ready()) {
      <form [formGroup]="form" (ngSubmit)="save()" class="form">
        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>General</mat-card-title></mat-card-header>
          <mat-card-content class="section">
            <mat-form-field appearance="outline">
              <mat-label>Platform name</mat-label>
              <input matInput formControlName="platform_name" />
              @if (form.controls.platform_name.hasError('required')) {
                <mat-error>Platform name is required.</mat-error>
              }
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Logo URL</mat-label>
              <input matInput formControlName="platform_logo_url" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Support email</mat-label>
              <input matInput type="email" formControlName="support_email" />
              @if (form.controls.support_email.hasError('email')) {
                <mat-error>Enter a valid email.</mat-error>
              }
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Support phone</mat-label>
              <input matInput formControlName="support_phone" />
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Defaults for new companies</mat-card-title></mat-card-header>
          <mat-card-content class="section">
            <mat-form-field appearance="outline">
              <mat-label>Default user limit</mat-label>
              <input matInput type="number" min="0" formControlName="default_user_limit" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Default API key limit</mat-label>
              <input matInput type="number" min="0" formControlName="default_api_key_limit" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Default API rate limit (req/min)</mat-label>
              <input matInput type="number" min="0" formControlName="default_api_rate_limit" />
            </mat-form-field>
          </mat-card-content>
        </mat-card>

        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Feature toggles</mat-card-title></mat-card-header>
          <mat-card-content class="toggles">
            <mat-slide-toggle formControlName="sms_module_enabled">SMS Module</mat-slide-toggle>
            <mat-slide-toggle formControlName="voice_module_enabled">Voice Module</mat-slide-toggle>
            <mat-slide-toggle formControlName="missed_call_module_enabled">Missed Call Module</mat-slide-toggle>
            <mat-slide-toggle formControlName="api_access_module_enabled">API Access Module</mat-slide-toggle>
          </mat-card-content>
        </mat-card>

        <mat-card appearance="outlined">
          <mat-card-header><mat-card-title>Security</mat-card-title></mat-card-header>
          <mat-card-content class="section">
            <mat-form-field appearance="outline">
              <mat-label>JWT expiry (minutes)</mat-label>
              <input matInput type="number" min="1" max="1440" formControlName="jwt_expiry_minutes" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Password min length</mat-label>
              <input matInput type="number" min="6" max="128" formControlName="password_min_length" />
            </mat-form-field>
            <div class="toggles">
              <mat-slide-toggle formControlName="password_require_uppercase">Require uppercase</mat-slide-toggle>
              <mat-slide-toggle formControlName="password_require_number">Require number</mat-slide-toggle>
              <mat-slide-toggle formControlName="password_require_symbol">Require symbol</mat-slide-toggle>
            </div>
          </mat-card-content>
        </mat-card>

        <div class="actions">
          <button mat-flat-button color="primary" type="submit" [disabled]="saving() || form.invalid">
            Save changes
          </button>
        </div>
      </form>
    }
  `,
  styles: [
    `
      .page-header { margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .form { display: flex; flex-direction: column; gap: 1rem; max-width: 48rem; }
      .section { display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 0.5rem 1rem; }
      .toggles { display: flex; flex-wrap: wrap; gap: 1rem; padding: 0.5rem 0; }
      .actions { margin-top: 0.5rem; }
      .state-card mat-card-content { display: flex; flex-direction: column; align-items: center; gap: 0.75rem; padding: 2rem; }
    `,
  ],
})
export class PlatformSettingsComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(SettingsService);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal(false);
  readonly ready = signal(false);

  readonly form = this.fb.nonNullable.group({
    platform_name: ['', [Validators.required]],
    platform_logo_url: this.fb.control<string | null>(null),
    support_email: this.fb.control<string | null>(null, [Validators.email]),
    support_phone: this.fb.control<string | null>(null),
    default_user_limit: this.fb.control<number | null>(null),
    default_api_key_limit: this.fb.control<number | null>(null),
    default_api_rate_limit: this.fb.control<number | null>(null),
    sms_module_enabled: [true],
    voice_module_enabled: [true],
    missed_call_module_enabled: [true],
    api_access_module_enabled: [true],
    jwt_expiry_minutes: [15],
    password_min_length: [8],
    password_require_uppercase: [true],
    password_require_number: [true],
    password_require_symbol: [false],
  });

  constructor() {
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.error.set(false);
    this.api.get().subscribe({
      next: (s) => {
        this.form.patchValue({
          platform_name: s.platform_name,
          platform_logo_url: s.platform_logo_url,
          support_email: s.support_email,
          support_phone: s.support_phone,
          default_user_limit: s.default_user_limit,
          default_api_key_limit: s.default_api_key_limit,
          default_api_rate_limit: s.default_api_rate_limit,
          sms_module_enabled: s.sms_module_enabled,
          voice_module_enabled: s.voice_module_enabled,
          missed_call_module_enabled: s.missed_call_module_enabled,
          api_access_module_enabled: s.api_access_module_enabled,
          jwt_expiry_minutes: s.jwt_expiry_minutes,
          password_min_length: s.password_min_length,
          password_require_uppercase: s.password_require_uppercase,
          password_require_number: s.password_require_number,
          password_require_symbol: s.password_require_symbol,
        });
        this.ready.set(true);
        this.loading.set(false);
      },
      error: () => {
        this.error.set(true);
        this.loading.set(false);
      },
    });
  }

  save(): void {
    if (this.form.invalid || this.saving()) {
      this.form.markAllAsTouched();
      return;
    }
    this.saving.set(true);
    this.api.update(this.form.getRawValue()).subscribe({
      next: () => {
        this.notify.success('Settings saved.');
        this.saving.set(false);
      },
      error: () => this.saving.set(false),
    });
  }
}
