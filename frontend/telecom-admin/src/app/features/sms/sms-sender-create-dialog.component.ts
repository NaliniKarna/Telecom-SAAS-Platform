import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';

import { SmsService } from './sms.service';
import { SmsSenderId } from './sms.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-sms-sender-create-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>{{ editing ? 'Edit sender ID' : 'Request sender ID' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline">
          <mat-label>Display name</mat-label>
          <input matInput formControlName="name" />
          @if (form.controls.name.hasError('required') && form.controls.name.touched) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Sender ID</mat-label>
          <input matInput formControlName="sender_id" maxlength="20" [readonly]="editing" />
          <mat-hint>The alphanumeric ID recipients see (max 20 chars).</mat-hint>
          @if (form.controls.sender_id.hasError('required') && form.controls.sender_id.touched) {
            <mat-error>Sender ID is required.</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Description</mat-label>
          <textarea matInput rows="2" formControlName="description"></textarea>
        </mat-form-field>
        @if (!editing) {
          <p class="note">New sender IDs are submitted for super-admin approval and start as <strong>Pending</strong>.</p>
        }
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="saving() || form.invalid">
        {{ editing ? 'Save' : 'Request' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [`.form { display: flex; flex-direction: column; gap: 0.5rem; min-width: 380px; padding-top: 0.5rem; } .note { color: var(--mat-sys-on-surface-variant); font-size: 0.85rem; margin: 0; }`],
})
export class SmsSenderCreateDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(SmsService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<SmsSenderCreateDialogComponent>);
  readonly data = inject<{ sender?: SmsSenderId }>(MAT_DIALOG_DATA, { optional: true });
  readonly saving = signal(false);
  readonly editing = !!this.data?.sender;

  readonly form = this.fb.nonNullable.group({
    name: [this.data?.sender?.name ?? '', [Validators.required]],
    sender_id: [this.data?.sender?.sender_id ?? '', [Validators.required, Validators.maxLength(20)]],
    description: this.fb.control<string | null>(this.data?.sender?.description ?? null),
  });

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const v = this.form.getRawValue();
    const done = {
      next: (s: SmsSenderId) => { this.notify.success(this.editing ? 'Sender ID updated.' : 'Sender ID requested.'); this.ref.close(s); },
      error: () => this.saving.set(false),
    };
    if (this.editing) {
      this.api.updateSenderId(this.data!.sender!.id, { name: v.name, description: v.description }).subscribe(done);
    } else {
      this.api.createSenderId({ name: v.name, sender_id: v.sender_id, description: v.description }).subscribe(done);
    }
  }
}
