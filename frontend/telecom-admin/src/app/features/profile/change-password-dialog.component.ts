import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators, AbstractControl, ValidationErrors } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ProfileService } from './profile.service';
import { NotificationService } from '../../core/services/notification.service';

function matchPasswords(group: AbstractControl): ValidationErrors | null {
  const n = group.get('newPassword')?.value;
  const c = group.get('confirmPassword')?.value;
  return n && c && n !== c ? { mismatch: true } : null;
}

@Component({
  selector: 'app-change-password-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>Change Password</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline">
          <mat-label>Current password</mat-label>
          <input matInput type="password" formControlName="currentPassword" autocomplete="current-password" />
          @if (form.controls.currentPassword.hasError('required') && form.controls.currentPassword.touched) {
            <mat-error>Current password is required.</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>New password</mat-label>
          <input matInput type="password" formControlName="newPassword" autocomplete="new-password" />
          @if (form.controls.newPassword.hasError('required') && form.controls.newPassword.touched) {
            <mat-error>New password is required.</mat-error>
          }
          @if (form.controls.newPassword.hasError('minlength')) {
            <mat-error>Must be at least 10 characters.</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Confirm new password</mat-label>
          <input matInput type="password" formControlName="confirmPassword" autocomplete="new-password" />
          @if (form.hasError('mismatch') && form.controls.confirmPassword.touched) {
            <mat-error>Passwords don't match.</mat-error>
          }
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)" [disabled]="saving()">Cancel</button>
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="saving() || form.invalid">
        {{ saving() ? 'Saving…' : 'Change password' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`.form { display: flex; flex-direction: column; gap: 0.5rem; min-width: 320px; padding-top: 0.5rem; }`],
})
export class ChangePasswordDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ProfileService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<ChangePasswordDialogComponent>);
  readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group(
    {
      currentPassword: ['', [Validators.required]],
      newPassword: ['', [Validators.required, Validators.minLength(10)]],
      confirmPassword: ['', [Validators.required]],
    },
    { validators: matchPasswords },
  );

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const { currentPassword, newPassword } = this.form.getRawValue();
    this.api.changePassword(currentPassword, newPassword).subscribe({
      next: () => {
        this.notify.success('Password changed. Please sign in again if prompted.');
        this.saving.set(false);
        this.ref.close(true);
      },
      error: () => this.saving.set(false),
    });
  }
}
