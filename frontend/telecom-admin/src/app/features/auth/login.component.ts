import { Component, inject, signal } from '@angular/core';
import {
  FormBuilder,
  ReactiveFormsModule,
  Validators,
} from '@angular/forms';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatIconModule } from '@angular/material/icon';

import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatCardModule,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressBarModule,
    MatIconModule,
  ],
  template: `
    <h1 class="login__title">Sign in</h1>
    <p class="login__subtitle">Access your telecom workspace.</p>

    @if (loading()) {
      <mat-progress-bar mode="indeterminate" />
    }

    @if (errorMessage()) {
      <div class="login__error" role="alert">
        <mat-icon>error_outline</mat-icon>
        <span>{{ errorMessage() }}</span>
      </div>
    }

    <form [formGroup]="form" (ngSubmit)="submit()" class="login__form">
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

      <mat-form-field appearance="outline">
        <mat-label>Password</mat-label>
        <input
          matInput
          type="password"
          formControlName="password"
          autocomplete="current-password"
        />
        @if (form.controls.password.hasError('required')) {
          <mat-error>Password is required.</mat-error>
        }
      </mat-form-field>

      <button
        mat-flat-button
        color="primary"
        type="submit"
        [disabled]="loading()"
        class="login__submit"
      >
        Sign in
      </button>
      <a routerLink="/auth/forgot-password" class="login__forgot">
        Forgot password?
      </a>
    </form>
  `,
  styles: [
    `
      .login__error {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        padding: 0.6rem 0.85rem;
        margin-bottom: 1rem;
        border-radius: 8px;
        background: var(--mat-sys-error-container);
        color: var(--mat-sys-on-error-container);
        font: var(--mat-sys-body-small);
      }
      .login__error mat-icon {
        font-size: 20px;
        height: 20px;
        width: 20px;
      }
      .login__title {
        font: var(--mat-sys-headline-small);
        margin: 0 0 0.25rem;
      }
      .login__subtitle {
        color: var(--mat-sys-on-surface-variant);
        margin: 0 0 1.5rem;
      }
      .login__form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-top: 1rem;
      }
      .login__submit {
        margin-top: 0.5rem;
        height: 44px;
      }
      .login__forgot {
        margin-top: 0.75rem;
        text-align: center;
        color: var(--mat-sys-primary);
        text-decoration: none;
        font: var(--mat-sys-body-small);
      }
    `,
  ],
})
export class LoginComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required]],
  });

  submit(): void {
    if (this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.errorMessage.set(null);
    this.auth.login(this.form.getRawValue()).subscribe({
      next: () => {
        // returnUrl wins if present; otherwise role-based landing.
        const returnUrl = this.route.snapshot.queryParamMap.get('returnUrl');
        void this.router.navigateByUrl(returnUrl ?? this.auth.landingRoute());
      },
      error: (err) => {
        this.loading.set(false);
        // 401 = bad credentials; show the server message if present,
        // otherwise a generic, non-enumerating fallback.
        this.errorMessage.set(
          err?.status === 401
            ? 'Invalid email or password.'
            : (err?.message ?? 'Unable to sign in. Please try again.'),
        );
      },
    });
  }
}