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

import { UsersService } from '../users/users.service';
import { NotificationService } from '../../core/services/notification.service';

// Mirrors the backend password policy (min length + upper/lower/digit).
function passwordStrength(control: AbstractControl): ValidationErrors | null {
  const v = String(control.value ?? '');
  if (v.length < 8) return { weak: 'at least 8 characters' };
  if (!/[A-Z]/.test(v)) return { weak: 'an uppercase letter' };
  if (!/[a-z]/.test(v)) return { weak: 'a lowercase letter' };
  if (!/[0-9]/.test(v)) return { weak: 'a digit' };
  return null;
}

@Component({
  selector: 'app-accept-invite',
  standalone: true,
  imports: [
    ReactiveFormsModule, RouterLink, MatFormFieldModule,
    MatInputModule, MatButtonModule, MatProgressBarModule,
  ],
  template: `
    <h1 class="ai__title">Accept your invite</h1>

    @if (!token) {
      <p class="ai__error">This invite link is invalid or incomplete.</p>
      <a mat-stroked-button routerLink="/auth/login">Go to sign in</a>
    } @else {
      <p class="ai__subtitle">Set a password to activate your account.</p>

      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

      <form [formGroup]="form" (ngSubmit)="submit()" class="ai__form">
        <mat-form-field appearance="outline">
          <mat-label>Password</mat-label>
          <input matInput type="password" formControlName="password"
            autocomplete="new-password" />
          @if (form.controls.password.hasError('required')) {
            <mat-error>Password is required.</mat-error>
          }
          @if (form.controls.password.hasError('weak')) {
            <mat-error>Password must contain {{ form.controls.password.getError('weak') }}.</mat-error>
          }
        </mat-form-field>
        <button mat-flat-button color="primary" type="submit"
          [disabled]="loading()" class="ai__submit">
          Activate account
        </button>
      </form>
    }
  `,
  styles: [
    `
      .ai__title { font: var(--mat-sys-headline-small); margin: 0 0 0.25rem; }
      .ai__subtitle { color: var(--mat-sys-on-surface-variant); margin: 0 0 1.5rem; }
      .ai__form { display: flex; flex-direction: column; gap: 0.5rem; margin-top: 1rem; }
      .ai__submit { margin-top: 0.5rem; height: 44px; }
      .ai__error { color: var(--mat-sys-error); margin: 0.5rem 0 1.25rem; }
    `,
  ],
})
export class AcceptInviteComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(UsersService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly notify = inject(NotificationService);

  readonly loading = signal(false);
  readonly token = this.route.snapshot.queryParamMap.get('token');

  readonly form = this.fb.nonNullable.group({
    password: ['', [Validators.required, passwordStrength]],
  });

  submit(): void {
    if (!this.token || this.form.invalid || this.loading()) {
      this.form.markAllAsTouched();
      return;
    }
    this.loading.set(true);
    this.api.acceptInvite(this.token, this.form.getRawValue().password).subscribe({
      next: () => {
        this.notify.success('Account activated. Please sign in.');
        void this.router.navigate(['/auth/login']);
      },
      error: () => this.loading.set(false),
    });
  }
}
