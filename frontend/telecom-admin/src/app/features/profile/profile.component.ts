import { Component, inject, signal } from '@angular/core';
import { ActivatedRoute } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatDialog } from '@angular/material/dialog';

import { AuthService } from '../../core/services/auth.service';
import { NotificationService } from '../../core/services/notification.service';
import { ProfileService } from './profile.service';
import { ChangePasswordDialogComponent } from './change-password-dialog.component';

@Component({
  selector: 'app-profile',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatIconModule,
  ],
  template: `
    <header class="page-header">
      <h1>My Profile</h1>
      <p>Manage your personal details and password.</p>
    </header>

    <div class="grid">
      <!-- Identity / name -->
      <mat-card appearance="outlined">
        <mat-card-header><mat-card-title>Personal details</mat-card-title></mat-card-header>
        <mat-card-content>
          <form [formGroup]="form" (ngSubmit)="save()" class="form">
            <div class="row">
              <mat-form-field appearance="outline">
                <mat-label>First name</mat-label>
                <input matInput formControlName="first_name" />
              </mat-form-field>
              <mat-form-field appearance="outline">
                <mat-label>Last name</mat-label>
                <input matInput formControlName="last_name" />
              </mat-form-field>
            </div>
            <mat-form-field appearance="outline">
              <mat-label>Email</mat-label>
              <input matInput [value]="auth.user()?.email ?? ''" disabled />
              <mat-hint>Email is your sign-in identity and can't be changed here.</mat-hint>
            </mat-form-field>
            <div class="actions">
              <button mat-flat-button color="primary" type="submit" [disabled]="saving()">Save changes</button>
            </div>
          </form>
        </mat-card-content>
      </mat-card>

      <!-- Avatar -->
      <mat-card appearance="outlined">
        <mat-card-header><mat-card-title>Profile photo</mat-card-title></mat-card-header>
        <mat-card-content class="avatar">
          <div class="avatar__preview">
            @if (auth.user()?.avatar_url) {
              <img [src]="auth.user()!.avatar_url!" alt="Profile photo" />
            } @else {
              <mat-icon>account_circle</mat-icon>
            }
          </div>
          <input #fileInput type="file" accept="image/png,image/jpeg,image/webp" hidden (change)="onFile($event)" />
          <button mat-stroked-button (click)="fileInput.click()" [disabled]="uploading()">
            <mat-icon>upload</mat-icon> {{ uploading() ? 'Uploading…' : 'Upload photo' }}
          </button>
          <p class="hint">PNG, JPEG or WebP. Max 2 MB.</p>
        </mat-card-content>
      </mat-card>

      <!-- Security -->
      <mat-card appearance="outlined">
        <mat-card-header><mat-card-title>Security</mat-card-title></mat-card-header>
        <mat-card-content class="security">
          <div>
            <div class="security__title">Password</div>
            <div class="hint">Change the password you use to sign in.</div>
          </div>
          <button mat-stroked-button (click)="openChangePassword()">
            <mat-icon>lock</mat-icon> Change password
          </button>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [
    `
      .page-header { margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 1rem; align-items: start; }
      .form { display: flex; flex-direction: column; gap: 0.5rem; }
      .row { display: flex; gap: 0.75rem; }
      .row mat-form-field { flex: 1; }
      .actions { margin-top: 0.5rem; }
      .avatar { display: flex; flex-direction: column; align-items: flex-start; gap: 0.75rem; }
      .avatar__preview {
        width: 110px; height: 110px; border-radius: 50%;
        border: 1px solid var(--mat-sys-outline-variant);
        display: flex; align-items: center; justify-content: center; overflow: hidden;
        background: var(--mat-sys-surface-container);
      }
      .avatar__preview img { width: 100%; height: 100%; object-fit: cover; }
      .avatar__preview mat-icon { font-size: 3.5rem; width: 3.5rem; height: 3.5rem; opacity: 0.4; }
      .security { display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
      .security__title { font-weight: 500; }
      .hint { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); margin: 0; }
    `,
  ],
})
export class ProfileComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ProfileService);
  protected readonly auth = inject(AuthService);
  private readonly notify = inject(NotificationService);
  private readonly dialog = inject(MatDialog);
  private readonly route = inject(ActivatedRoute);

  readonly saving = signal(false);
  readonly uploading = signal(false);

  readonly form = this.fb.nonNullable.group({
    first_name: this.fb.control<string | null>(null),
    last_name: this.fb.control<string | null>(null),
  });

  constructor() {
    const u = this.auth.user();
    this.form.patchValue({ first_name: u?.first_name ?? null, last_name: u?.last_name ?? null });
    // Auto-open the change-password dialog when arriving via the header menu
    // "Change Password" action (B1 routes it to /profile?changePassword=1).
    if (this.route.snapshot.queryParamMap.get('changePassword') === '1') {
      queueMicrotask(() => this.openChangePassword());
    }
  }

  save(): void {
    if (this.saving()) return;
    this.saving.set(true);
    this.api.updateProfile(this.form.getRawValue()).subscribe({
      next: () => {
        this.auth.fetchMe().subscribe();
        this.notify.success('Profile updated.');
        this.saving.set(false);
      },
      error: () => this.saving.set(false),
    });
  }

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.uploading.set(true);
    this.api.uploadAvatar(file).subscribe({
      next: () => {
        this.auth.fetchMe().subscribe();
        this.notify.success('Photo updated.');
        this.uploading.set(false);
        input.value = '';
      },
      error: () => { this.uploading.set(false); input.value = ''; },
    });
  }

  openChangePassword(): void {
    this.dialog.open(ChangePasswordDialogComponent, { autoFocus: false });
  }
}
