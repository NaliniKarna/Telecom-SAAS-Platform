import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { PlansService } from './plans.service';
import { NotificationService } from '../../core/services/notification.service';

// Mirrors the backend code rule.
function codeValidator(control: AbstractControl): ValidationErrors | null {
  const v = String(control.value ?? '');
  if (!v) return null;
  return /^[a-z0-9]([a-z0-9_-]*[a-z0-9])?$/.test(v) ? null : { code: true };
}

@Component({
  selector: 'app-plan-form',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatSlideToggleModule,
    MatButtonModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <h1>{{ editId() ? 'Edit plan' : 'New plan' }}</h1>
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    <form [formGroup]="form" (ngSubmit)="submit()" class="form">
      <section class="group">
        <h2>General</h2>
        <mat-form-field appearance="outline">
          <mat-label>Plan name</mat-label>
          <input matInput formControlName="name" />
          @if (form.controls.name.hasError('required')) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>

        @if (!editId()) {
          <mat-form-field appearance="outline">
            <mat-label>Plan code</mat-label>
            <input matInput formControlName="code" />
            <mat-hint>Lowercase letters, numbers, hyphens/underscores. Immutable once set.</mat-hint>
            @if (form.controls.code.hasError('required')) {
              <mat-error>Code is required.</mat-error>
            }
            @if (form.controls.code.hasError('code')) {
              <mat-error>Invalid code format.</mat-error>
            }
          </mat-form-field>
        }

        <mat-form-field appearance="outline">
          <mat-label>Description</mat-label>
          <textarea matInput rows="3" formControlName="description"></textarea>
        </mat-form-field>

        <mat-slide-toggle formControlName="is_active">Active</mat-slide-toggle>
      </section>

      <section class="group">
        <h2>Limits</h2>
        <p class="hint">Leave a field blank for unlimited.</p>
        <div class="grid">
          <mat-form-field appearance="outline">
            <mat-label>Max users</mat-label>
            <input matInput type="number" min="0" formControlName="default_max_users" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Max API keys</mat-label>
            <input matInput type="number" min="0" formControlName="default_max_api_keys" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>API rate limit (req/min)</mat-label>
            <input matInput type="number" min="0" formControlName="default_api_rate_limit" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Monthly SMS limit</mat-label>
            <input matInput type="number" min="0" formControlName="default_monthly_sms_limit" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Monthly voice minutes</mat-label>
            <input matInput type="number" min="0" formControlName="default_monthly_voice_minutes" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Monthly TTS characters</mat-label>
            <input matInput type="number" min="0" formControlName="default_monthly_tts_characters" />
            <mat-hint>Ceiling only — not yet enforced by usage metering.</mat-hint>
          </mat-form-field>
        </div>
      </section>

      <section class="group">
        <h2>Features</h2>
        <div class="toggles">
          <mat-slide-toggle formControlName="default_sms_enabled">SMS</mat-slide-toggle>
          <mat-slide-toggle formControlName="default_voice_enabled">Voice</mat-slide-toggle>
          <mat-slide-toggle formControlName="default_missed_call_enabled">Missed Call</mat-slide-toggle>
          <mat-slide-toggle formControlName="default_freepbx_enabled">FreePBX</mat-slide-toggle>
          <mat-slide-toggle formControlName="default_api_access_enabled">API Access</mat-slide-toggle>
          <mat-slide-toggle formControlName="default_ai_voice_enabled">AI Voice</mat-slide-toggle>
        </div>
      </section>

      <div class="actions">
        <a mat-stroked-button routerLink="/subscription-plans">Cancel</a>
        <button mat-flat-button color="primary" type="submit" [disabled]="loading()">
          {{ editId() ? 'Save changes' : 'Create plan' }}
        </button>
      </div>
    </form>
  `,
  styles: [
    `
      .page-header h1 {
        font: var(--mat-sys-headline-medium);
        margin: 0 0 1.5rem;
      }
      .form {
        display: flex;
        flex-direction: column;
        gap: 1.5rem;
        max-width: 46rem;
      }
      .group {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
      }
      .group h2 {
        font: var(--mat-sys-title-small);
        color: var(--mat-sys-on-surface-variant);
        margin: 0 0 0.25rem;
      }
      .hint {
        color: var(--mat-sys-on-surface-variant);
        font: var(--mat-sys-body-small);
        margin: 0 0 0.25rem;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 0.5rem 1rem;
      }
      .toggles {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
        gap: 0.75rem;
        padding: 0.5rem 0;
      }
      .actions {
        display: flex;
        gap: 0.75rem;
        margin-top: 0.5rem;
      }
    `,
  ],
})
export class PlanFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(PlansService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly editId = signal<string | null>(
    this.route.snapshot.paramMap.get('id'),
  );

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    code: ['', [Validators.required, codeValidator]],
    description: this.fb.control<string | null>(null),
    is_active: [true],
    default_max_users: this.fb.control<number | null>(null),
    default_api_rate_limit: this.fb.control<number | null>(null),
    default_max_api_keys: this.fb.control<number | null>(null),
    default_monthly_sms_limit: this.fb.control<number | null>(null),
    default_monthly_voice_minutes: this.fb.control<number | null>(null),
    default_monthly_tts_characters: this.fb.control<number | null>(null),
    default_sms_enabled: [false],
    default_voice_enabled: [false],
    default_missed_call_enabled: [false],
    default_freepbx_enabled: [false],
    default_api_access_enabled: [false],
    default_ai_voice_enabled: [false],
  });

  constructor() {
    const id = this.editId();
    if (id) {
      this.form.controls.code.disable();
      this.loading.set(true);
      this.api.get(id).subscribe({
        next: (res) => {
          const p = res.data;
          this.form.patchValue({
            name: p.name,
            code: p.code,
            description: p.description,
            is_active: p.is_active,
            default_max_users: p.default_max_users,
            default_api_rate_limit: p.default_api_rate_limit,
            default_max_api_keys: p.default_max_api_keys,
            default_monthly_sms_limit: p.default_monthly_sms_limit,
            default_monthly_voice_minutes: p.default_monthly_voice_minutes,
            default_monthly_tts_characters: p.default_monthly_tts_characters,
            default_sms_enabled: p.default_sms_enabled,
            default_voice_enabled: p.default_voice_enabled,
            default_missed_call_enabled: p.default_missed_call_enabled,
            default_freepbx_enabled: p.default_freepbx_enabled,
            default_api_access_enabled: p.default_api_access_enabled,
            default_ai_voice_enabled: p.default_ai_voice_enabled,
          });
          this.loading.set(false);
        },
        error: () => this.loading.set(false),
      });
    }
  }

  submit(): void {
    if (this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    const id = this.editId();
    const raw = this.form.getRawValue();

    const common = {
      name: raw.name,
      description: raw.description || null,
      is_active: raw.is_active,
      default_max_users: raw.default_max_users,
      default_api_rate_limit: raw.default_api_rate_limit,
      default_max_api_keys: raw.default_max_api_keys,
      default_monthly_sms_limit: raw.default_monthly_sms_limit,
      default_monthly_voice_minutes: raw.default_monthly_voice_minutes,
      default_monthly_tts_characters: raw.default_monthly_tts_characters,
      default_sms_enabled: raw.default_sms_enabled,
      default_voice_enabled: raw.default_voice_enabled,
      default_missed_call_enabled: raw.default_missed_call_enabled,
      default_freepbx_enabled: raw.default_freepbx_enabled,
      default_api_access_enabled: raw.default_api_access_enabled,
      default_ai_voice_enabled: raw.default_ai_voice_enabled,
    };

    if (id) {
      this.api.update(id, common).subscribe({
        next: () => {
          this.notify.success('Plan updated.');
          void this.router.navigate(['/subscription-plans', id]);
        },
        error: () => this.loading.set(false),
      });
    } else {
      this.api.create({ ...common, code: raw.code }).subscribe({
        next: (p) => {
          this.notify.success('Plan created.');
          void this.router.navigate(['/subscription-plans', p.id]);
        },
        error: () => this.loading.set(false),
      });
    }
  }
}