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
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';

// Mirrors the backend password policy (length + upper/lower/digit).
function passwordStrength(control: AbstractControl): ValidationErrors | null {
  const v = String(control.value ?? '');
  if (v.length < 10) return { weak: 'at least 10 characters' };
  if (!/[A-Z]/.test(v)) return { weak: 'an uppercase letter' };
  if (!/[a-z]/.test(v)) return { weak: 'a lowercase letter' };
  if (!/[0-9]/.test(v)) return { weak: 'a digit' };
  return null;
}

@Component({
  selector: 'app-reset-password',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressBarModule,
  ],
  template: `
    <h1 class="rp__title">Reset password</h1>

    @if (!token) {
      <p class="rp__error">
        This reset link is invalid or incomplete. Request a new one.
      </p>
      <a mat-stroked-button routerLink="/auth/forgot-password">
        Request a new link
      </a>
    } @else {
      <p class="rp__subtitle">Choose a new password for your account.</p>

      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }

      <form [formGroup]="form" (ngSubmit)="submit()" class="rp__form">
        <mat-form-field appearance="outline">
          <mat-label>New password</mat-label>
          <input
            matInput
            type="password"
            formControlName="newPassword"
            autocomplete="new-password"
          />
          @if (form.controls.newPassword.hasError('required')) {
            <mat-error>Password is required.</mat-error>
          }
          @if (form.controls.newPassword.hasError('weak')) {
            <mat-error>
              Password must contain {{ form.controls.newPassword.getError('weak') }}.
            </mat-error>
          }
        </mat-form-field>

        <button
          mat-flat-button
          color="primary"
          type="submit"
          [disabled]="loading()"
          class="rp__submit"
        >
          Set new password
        </button>
      </form>
    }
  `,
  styles: [
    `
      .rp__title {
        font: var(--mat-sys-headline-small);
        margin: 0 0 0.25rem;
      }
      .rp__subtitle {
        color: var(--mat-sys-on-surface-variant);
        margin: 0 0 1.5rem;
      }
      .rp__form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-top: 1rem;
      }
      .rp__submit {
        margin-top: 0.5rem;
        height: 44px;
      }
      .rp__error {
        color: var(--mat-sys-error);
        margin: 0.5rem 0 1.25rem;
      }
    `,
  ],
})
export class ResetPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly token = this.route.snapshot.queryParamMap.get('token');

  readonly form = this.fb.nonNullable.group({
    newPassword: ['', [Validators.required, passwordStrength]],
  });

  submit(): void {
    if (!this.token || this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.auth
      .resetPassword(this.token, this.form.getRawValue().newPassword)
      .subscribe({
        next: () => {
          this.notify.success('Password updated. Please sign in.');
          void this.router.navigate(['/auth/login']);
        },
        error: () => this.loading.set(false),
      });
  }
}