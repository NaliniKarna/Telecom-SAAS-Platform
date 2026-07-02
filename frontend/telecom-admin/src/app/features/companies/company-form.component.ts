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
import { MatSelectModule } from '@angular/material/select';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { CompaniesService } from './companies.service';
import { SubscriptionPlan } from './company.models';
import { NotificationService } from '../../core/services/notification.service';

// Mirrors the backend slug rule.
function slugValidator(control: AbstractControl): ValidationErrors | null {
  const v = String(control.value ?? '');
  if (!v) return null;
  return /^[a-z0-9]([a-z0-9-]*[a-z0-9])?$/.test(v) ? null : { slug: true };
}

@Component({
  selector: 'app-company-form',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatSelectModule,
    MatSlideToggleModule,
    MatButtonModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <h1>{{ editId() ? 'Edit company' : 'New company' }}</h1>
    </header>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    <form [formGroup]="form" (ngSubmit)="submit()" class="form">
      <section class="group">
        <h2>Details</h2>
        <mat-form-field appearance="outline">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" />
          @if (form.controls.name.hasError('required')) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>

        @if (!editId()) {
          <mat-form-field appearance="outline">
            <mat-label>Slug</mat-label>
            <input matInput formControlName="slug" />
            <mat-hint>Lowercase letters, numbers, hyphens. Immutable once set.</mat-hint>
            @if (form.controls.slug.hasError('required')) {
              <mat-error>Slug is required.</mat-error>
            }
            @if (form.controls.slug.hasError('slug')) {
              <mat-error>Invalid slug format.</mat-error>
            }
          </mat-form-field>
        }

        <mat-form-field appearance="outline">
          <mat-label>Subscription plan</mat-label>
          <mat-select formControlName="plan_id">
            <mat-option [value]="null">— None —</mat-option>
            @for (p of plans(); track p.id) {
              <mat-option [value]="p.id">{{ p.name }}</mat-option>
            }
          </mat-select>
        </mat-form-field>
      </section>

      <section class="group">
        <h2>Contact</h2>
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
      </section>

      <section class="group">
        <h2>Entitlements</h2>
        <div class="toggles">
          <mat-slide-toggle formControlName="sms_enabled">SMS</mat-slide-toggle>
          <mat-slide-toggle formControlName="voice_enabled">Voice</mat-slide-toggle>
          <mat-slide-toggle formControlName="missed_call_enabled">Missed Call</mat-slide-toggle>
          <mat-slide-toggle formControlName="freepbx_enabled">FreePBX</mat-slide-toggle>
        </div>
      </section>

      <section class="group">
        <h2>Limits</h2>
        <mat-form-field appearance="outline">
          <mat-label>Max users</mat-label>
          <input matInput type="number" min="0" formControlName="max_users" />
          <mat-hint>Leave blank for unlimited.</mat-hint>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>API rate limit (req/min)</mat-label>
          <input matInput type="number" min="0" formControlName="api_rate_limit" />
          <mat-hint>Leave blank for unlimited.</mat-hint>
        </mat-form-field>
      </section>

      <div class="actions">
        <a mat-stroked-button routerLink="/companies">Cancel</a>
        <button mat-flat-button color="primary" type="submit" [disabled]="loading()">
          {{ editId() ? 'Save changes' : 'Create company' }}
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
        max-width: 40rem;
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
      .toggles {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
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
export class CompanyFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(CompaniesService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly plans = signal<SubscriptionPlan[]>([]);
  readonly editId = signal<string | null>(
    this.route.snapshot.paramMap.get('id'),
  );

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    slug: ['', [Validators.required, slugValidator]],
    plan_id: this.fb.control<string | null>(null),
    contact_email: this.fb.control<string | null>(null, [Validators.email]),
    contact_phone: this.fb.control<string | null>(null),
    sms_enabled: [false],
    voice_enabled: [false],
    missed_call_enabled: [false],
    freepbx_enabled: [false],
    max_users: this.fb.control<number | null>(null),
    api_rate_limit: this.fb.control<number | null>(null),
  });

  constructor() {
    this.api.listPlans().subscribe({ next: (p) => this.plans.set(p) });

    const id = this.editId();
    if (id) {
      this.form.controls.slug.disable();
      this.loading.set(true);
      this.api.get(id).subscribe({
        next: (c) => {
          this.form.patchValue({
            name: c.name,
            slug: c.slug,
            plan_id: c.plan_id,
            contact_email: c.contact_email,
            contact_phone: c.contact_phone,
            sms_enabled: c.sms_enabled,
            voice_enabled: c.voice_enabled,
            missed_call_enabled: c.missed_call_enabled,
            freepbx_enabled: c.freepbx_enabled,
            max_users: c.max_users,
            api_rate_limit: c.api_rate_limit,
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

    // Shared payload of entitlements/limits/contact + plan.
    const common = {
      plan_id: raw.plan_id,
      contact_email: raw.contact_email || null,
      contact_phone: raw.contact_phone || null,
      sms_enabled: raw.sms_enabled,
      voice_enabled: raw.voice_enabled,
      missed_call_enabled: raw.missed_call_enabled,
      freepbx_enabled: raw.freepbx_enabled,
      max_users: raw.max_users,
      api_rate_limit: raw.api_rate_limit,
    };

    if (id) {
      this.api.update(id, { name: raw.name, ...common }).subscribe({
        next: () => {
          this.notify.success('Company updated.');
          void this.router.navigate(['/companies', id]);
        },
        error: () => this.loading.set(false),
      });
    } else {
      this.api
        .create({ name: raw.name, slug: raw.slug, ...common })
        .subscribe({
          next: (c) => {
            this.notify.success('Company created.');
            void this.router.navigate(['/companies', c.id]);
          },
          error: () => this.loading.set(false),
        });
    }
  }
}
