import { Component, inject, signal } from '@angular/core';
import {
  AbstractControl,
  FormBuilder,
  ReactiveFormsModule,
  ValidationErrors,
  Validators,
} from '@angular/forms';
import { RouterLink } from '@angular/router';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatIconModule } from '@angular/material/icon';

import { AuthService } from '../../core/services/auth.service';

/** Passwords-match validator for the form group. */
function passwordsMatch(group: AbstractControl): ValidationErrors | null {
  const pw = group.get('password')?.value;
  const confirm = group.get('confirmPassword')?.value;
  return pw && confirm && pw !== confirm ? { mismatch: true } : null;
}

/**
 * Public company self-registration. Renders inside the AuthLayout shell (child
 * of /auth, so guestGuard applies). On success it shows a "verify your email"
 * confirmation rather than logging in — the account is pending approval.
 */
@Component({
  selector: 'app-register-company',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    MatFormFieldModule,
    MatInputModule,
    MatButtonModule,
    MatProgressBarModule,
    MatIconModule,
  ],
  template: `
    @if (submitted()) {
      <div class="reg__done">
        <mat-icon class="reg__done-icon">mark_email_read</mat-icon>
        <h1 class="reg__title">Check your email</h1>
        <p class="reg__subtitle">
          We've sent a verification link to
          <strong>{{ submittedEmail() }}</strong>. Verify your email to complete
          registration — then a platform administrator will review and approve
          your company before you can sign in.
        </p>
        <a routerLink="/auth/login" mat-flat-button color="primary" class="reg__submit">
          Back to sign in
        </a>
      </div>
    } @else {
      <h1 class="reg__title">Register your company</h1>
      <p class="reg__subtitle">
        Create a company account. After you verify your email, an administrator
        reviews and approves it before access is granted.
      </p>

      @if (loading()) {
        <mat-progress-bar mode="indeterminate" />
      }

      @if (errorMessage()) {
        <div class="reg__error" role="alert">
          <mat-icon>error_outline</mat-icon>
          <span>{{ errorMessage() }}</span>
        </div>
      }

      <form [formGroup]="form" (ngSubmit)="submit()" class="reg__form">
        <mat-form-field appearance="outline">
          <mat-label>Company name</mat-label>
          <input matInput formControlName="company_name" autocomplete="organization" />
          @if (form.controls.company_name.hasError('required')) {
            <mat-error>Company name is required.</mat-error>
          }
          @if (form.controls.company_name.hasError('minlength')) {
            <mat-error>Use at least 2 characters.</mat-error>
          }
        </mat-form-field>

        <div class="reg__row">
          <mat-form-field appearance="outline">
            <mat-label>First name</mat-label>
            <input matInput formControlName="admin_first_name" autocomplete="given-name" />
            @if (form.controls.admin_first_name.hasError('required')) {
              <mat-error>First name is required.</mat-error>
            }
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Last name</mat-label>
            <input matInput formControlName="admin_last_name" autocomplete="family-name" />
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Work email</mat-label>
          <input matInput type="email" formControlName="admin_email" autocomplete="email" />
          @if (form.controls.admin_email.hasError('required')) {
            <mat-error>Email is required.</mat-error>
          }
          @if (form.controls.admin_email.hasError('email')) {
            <mat-error>Enter a valid email.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Phone</mat-label>
          <!--<span matPrefix class="phone-prefix"> +977&nbsp;</span>-->
          <input matInput formControlName="contact_phone" autocomplete="tel"
            placeholder="98XXXXXXXX" maxlength="10" />
          @if (form.controls.contact_phone.hasError('pattern')) {
            <mat-error>Enter a valid 10-digit phone number.</mat-error>
          }
          @if (form.controls.contact_phone.hasError('maxlength')) {
            <mat-error>Phone number cannot exceed 10 digits.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Password</mat-label>
          <input matInput type="password" formControlName="password" autocomplete="new-password" />
          @if (form.controls.password.hasError('required')) {
            <mat-error>Password is required.</mat-error>
          }
          @if (form.controls.password.hasError('minlength')) {
            <mat-error>Use at least 10 characters.</mat-error>
          }
        </mat-form-field>

        <mat-form-field appearance="outline">
          <mat-label>Confirm password</mat-label>
          <input matInput type="password" formControlName="confirmPassword" autocomplete="new-password" />
          @if (form.hasError('mismatch') && form.controls.confirmPassword.touched) {
            <mat-error>Passwords do not match.</mat-error>
          }
        </mat-form-field>

        <button
          mat-flat-button
          color="primary"
          type="submit"
          [disabled]="loading()"
          class="reg__submit"
        >
          Register company
        </button>
        <a routerLink="/auth/login" class="reg__signin">Already have an account? Sign in</a>
      </form>
    }
  `,
  styles: [
    `
      .reg__title {
        font: var(--mat-sys-headline-small);
        margin: 0 0 0.25rem;
      }
      .reg__subtitle {
        color: var(--mat-sys-on-surface-variant);
        margin: 0 0 1rem;
      }
      .reg__form {
        display: flex;
        flex-direction: column;
        gap: 0.5rem;
        margin-top: 1rem;
      }
      .reg__row {
        display: flex;
        gap: 0.75rem;
      }
      .reg__row mat-form-field {
        flex: 1;
      }
      .reg__submit {
        margin-top: 0.5rem;
        height: 44px;
      }
      .reg__signin {
        margin-top: 0.75rem;
        text-align: center;
        color: var(--mat-sys-primary);
        text-decoration: none;
        font: var(--mat-sys-body-small);
      }
      .reg__error {
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
      .reg__error mat-icon {
        font-size: 20px;
        height: 20px;
        width: 20px;
      }
      .reg__done {
        text-align: center;
        padding: 1rem 0;
      }
      .reg__done-icon {
        font-size: 48px;
        height: 48px;
        width: 48px;
        color: var(--mat-sys-primary);
        margin-bottom: 0.5rem;
      }
      .reg__done .reg__submit {
        display: inline-flex;
        margin-top: 1.25rem;
      }
      .phone-prefix {
        font-weight: 600;
        color: var(--mat-sys-on-surface);
      }

      @media (max-width: 480px) {
        .reg__row {
          flex-direction: column;
          gap: 0.5rem;
        }
      }
    `,
  ],
})
export class RegisterCompanyComponent {
  private readonly fb = inject(FormBuilder);
  private readonly auth = inject(AuthService);

  readonly loading = signal(false);
  readonly errorMessage = signal<string | null>(null);
  readonly submitted = signal(false);
  readonly submittedEmail = signal('');

  readonly form = this.fb.nonNullable.group(
    {
      company_name: ['', [Validators.required, Validators.minLength(2)]],
      admin_first_name: ['', [Validators.required]],
      admin_last_name: [''],
      admin_email: ['', [Validators.required, Validators.email]],
      contact_phone: ['', [
        Validators.maxLength(10),
        Validators.pattern(/^[0-9]{0,10}$/),
      ]],
      password: ['', [Validators.required, Validators.minLength(10)]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: passwordsMatch },
  );

  submit(): void {
    if (this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.errorMessage.set(null);

    const v = this.form.getRawValue();

    // Auto-prefix +977 if the user entered a phone number.
    const rawPhone = v.contact_phone?.replace(/\D/g, '') || '';
    const fullPhone = rawPhone ? `+977${rawPhone}` : null;

    this.auth
      .registerCompany({
        company_name: v.company_name,
        admin_first_name: v.admin_first_name,
        admin_last_name: v.admin_last_name || null,
        admin_email: v.admin_email,
        password: v.password,
        contact_phone: fullPhone,
      })
      .subscribe({
        next: () => {
          this.submittedEmail.set(v.admin_email);
          this.submitted.set(true);
        },
        error: (err) => {
          this.loading.set(false);
          const serverMsg =
            err?.error?.errors?.[0]?.message ?? err?.message ?? null;
          this.errorMessage.set(
            err?.status === 409
              ? (serverMsg ??
                'An account with that email already exists. Try signing in.')
              : (serverMsg ?? 'Unable to register right now. Please try again.'),
          );
        },
      });
  }
}