import { Component, inject, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-forgot-password',
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
    <h1 class="fp__title">Forgot password</h1>
    <p class="fp__subtitle">
      Enter your email and we'll send a reset link if an account exists.
    </p>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (sent()) {
      <p class="fp__sent">
        If an account exists for that email, a reset link has been sent. Check
        your inbox.
      </p>
      <a mat-stroked-button routerLink="/auth/login">Back to sign in</a>
    } @else {
      <form [formGroup]="form" (ngSubmit)="submit()" class="fp__form">
        <mat-form-field appearance="outline">
          <mat-label>Email</mat-label>
          <input matInput type="email" formControlName="email" autocomplete="username" />
          @if (form.controls.email.hasError('required')) {
            <mat-error>Email is required.</mat-error>
          }
          @if (form.controls.email.hasError('email')) {
            <mat-error>Enter a valid email.</mat-error>
          }
        </mat-form-field>

        <button
          mat-flat-button
          color="primary"
          type="submit"
          [disabled]="loading()"
          class="fp__submit"
        >
          Send reset link
        </button>
        <a routerLink="/auth/login" class="fp__back">Back to sign in</a>
      </form>
    }
  `,
  styles: [
    `
      .fp__title {
        font: var(--mat-sys-headline-small);
        margin: 0 0 0.25rem;
      }
      .fp__subtitle {
        color: var(--mat-sys-on-surface-variant);
        margin: 0 0 1.5rem;
      }
      .fp__form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-top: 1rem;
      }
      .fp__submit {
        margin-top: 0.5rem;
        height: 44px;
      }
      .fp__back {
        margin-top: 0.75rem;
        text-align: center;
        color: var(--mat-sys-primary);
        text-decoration: none;
      }
      .fp__sent {
        color: var(--mat-sys-on-surface-variant);
        margin: 1rem 0 1.25rem;
      }
    `,
  ],
})
export class ForgotPasswordComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  readonly loading = signal(false);
  readonly sent = signal(false);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
  });

  submit(): void {
    if (this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.auth.forgotPassword(this.form.getRawValue().email).subscribe({
      // Always show the same confirmation — the backend is enumeration-safe.
      next: () => {
        this.loading.set(false);
        this.sent.set(true);
      },
      error: () => {
        this.loading.set(false);
        this.sent.set(true);
      },
    });
  }
}