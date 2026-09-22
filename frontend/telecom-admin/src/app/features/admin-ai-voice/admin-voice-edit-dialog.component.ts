import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';

import { AdminAiVoiceService } from './admin-ai-voice.service';
import { AdminVoice } from './admin-ai-voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-admin-voice-edit-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>{{ editing ? 'Edit voice' : 'New voice' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" />
          @if (form.controls.name.hasError('required') && form.controls.name.touched) { <mat-error>Name is required.</mat-error> }
        </mat-form-field>

        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Language</mat-label>
            <input matInput formControlName="language" placeholder="ne" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Gender (optional)</mat-label>
            <mat-select formControlName="gender">
              <mat-option [value]="null">—</mat-option>
              <mat-option value="female">Female</mat-option>
              <mat-option value="male">Male</mat-option>
            </mat-select>
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Description (optional)</mat-label>
          <input matInput formControlName="description" />
        </mat-form-field>

        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Provider</mat-label>
            <input matInput formControlName="provider" placeholder="elevenlabs" />
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Provider voice ID</mat-label>
            <input matInput formControlName="provider_voice_id" />
            @if (form.controls.provider_voice_id.hasError('required') && form.controls.provider_voice_id.touched) {
              <mat-error>Required — the exact voice ID from the provider.</mat-error>
            }
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select formControlName="status">
            <mat-option value="active">Active</mat-option>
            <mat-option value="inactive">Inactive</mat-option>
          </mat-select>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="saving() || form.invalid">
        {{ editing ? 'Save' : 'Create' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`
    .form { display: flex; flex-direction: column; gap: .5rem; min-width: 440px; padding-top: .5rem; }
    .row { display: flex; gap: .75rem; }
    .row mat-form-field { flex: 1 1 0; }
  `],
})
export class AdminVoiceEditDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(AdminAiVoiceService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<AdminVoiceEditDialogComponent>);
  readonly data = inject<{ voice?: AdminVoice }>(MAT_DIALOG_DATA, { optional: true });
  readonly saving = signal(false);
  readonly editing = !!this.data?.voice;

  readonly form = this.fb.nonNullable.group({
    name: [this.data?.voice?.name ?? '', [Validators.required]],
    language: [this.data?.voice?.language ?? 'ne', [Validators.required]],
    gender: this.fb.control<string | null>(this.data?.voice?.gender ?? null),
    description: [this.data?.voice?.description ?? ''],
    provider: [this.data?.voice?.provider ?? 'elevenlabs', [Validators.required]],
    provider_voice_id: [this.data?.voice?.provider_voice_id ?? '', [Validators.required]],
    status: this.fb.nonNullable.control<'active' | 'inactive'>(this.data?.voice?.status ?? 'active'),
  });

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const v = this.form.getRawValue();
    const done = {
      next: (voice: AdminVoice) => { this.notify.success(this.editing ? 'Voice updated.' : 'Voice created.'); this.ref.close(voice); },
      error: () => this.saving.set(false),
    };
    if (this.editing) {
      this.api.updateVoice(this.data!.voice!.id, v).subscribe(done);
    } else {
      this.api.createVoice(v).subscribe(done);
    }
  }
}
