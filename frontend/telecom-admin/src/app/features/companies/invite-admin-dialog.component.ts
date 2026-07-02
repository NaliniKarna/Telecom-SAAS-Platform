import { Component, inject } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-invite-admin-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule,
    MatInputModule, MatButtonModule,
  ],
  template: `
    <h2 mat-dialog-title>Invite company admin</h2>
    <mat-dialog-content>
      <p class="hint">
        Creates a pending Company Admin for this company and emails an invite to
        set a password. Use this to bootstrap a company's first admin.
      </p>
      <div class="form">
        <mat-form-field appearance="outline">
          <mat-label>Email</mat-label>
          <input matInput type="email" [formControl]="form.controls.email" />
          @if (form.controls.email.hasError('required')) {
            <mat-error>Email is required.</mat-error>
          }
          @if (form.controls.email.hasError('email')) {
            <mat-error>Enter a valid email.</mat-error>
          }
        </mat-form-field>
        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>First name</mat-label>
            <input matInput [formControl]="form.controls.first_name" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Last name</mat-label>
            <input matInput [formControl]="form.controls.last_name" />
          </mat-form-field>
        </div>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-stroked-button (click)="cancel()">Cancel</button>
      <button mat-flat-button color="primary" (click)="send()" [disabled]="form.invalid">
        Send invite
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .hint { color: var(--mat-sys-on-surface-variant); margin: 0 0 1rem; }
      .form { display: flex; flex-direction: column; gap: 0.25rem; min-width: 360px; }
      .row { display: flex; gap: 0.75rem; }
      .row mat-form-field { flex: 1; }
    `,
  ],
})
export class InviteAdminDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly ref = inject(MatDialogRef<InviteAdminDialogComponent>);

  readonly form = this.fb.nonNullable.group({
    email: ['', [Validators.required, Validators.email]],
    first_name: [''],
    last_name: [''],
  });

  send(): void {
    if (this.form.invalid) { this.form.markAllAsTouched(); return; }
    const v = this.form.getRawValue();
    this.ref.close({
      email: v.email,
      first_name: v.first_name || null,
      last_name: v.last_name || null,
    });
  }
  cancel(): void { this.ref.close(null); }
}
