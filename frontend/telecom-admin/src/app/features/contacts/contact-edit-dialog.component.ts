import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule, MatChipInputEvent } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';

import { ContactService } from './contact.service';
import { Contact, ContactStatus } from './contact.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-contact-edit-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatChipsModule, MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ data?.id ? 'Edit contact' : 'New contact' }}</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
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
        <div class="row">
          <mat-form-field appearance="outline">
            <mat-label>Mobile number</mat-label>
            <input matInput formControlName="mobile" placeholder="98XXXXXXXX" />
            <mat-hint>Auto-converted to +977</mat-hint>
          </mat-form-field>
          <mat-form-field appearance="outline">
            <mat-label>Landline number</mat-label>
            <input matInput formControlName="landline" placeholder="01-XXXXXXX" />
          </mat-form-field>
        </div>
        <mat-form-field appearance="outline">
          <mat-label>Email</mat-label>
          <input matInput type="email" formControlName="email" />
          @if (form.controls.email.hasError('email')) { <mat-error>Enter a valid email.</mat-error> }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Tags</mat-label>
          <mat-chip-grid #grid>
            @for (tag of tags(); track tag) {
              <mat-chip-row (removed)="removeTag(tag)">{{ tag }}<button matChipRemove><mat-icon>cancel</mat-icon></button></mat-chip-row>
            }
          </mat-chip-grid>
          <input placeholder="Add tag…" [matChipInputFor]="grid" (matChipInputTokenEnd)="addTag($event)" />
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select formControlName="status">
            <mat-option value="active">Active</mat-option>
            <mat-option value="inactive">Inactive</mat-option>
            <mat-option value="unsubscribed">Unsubscribed</mat-option>
          </mat-select>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Notes</mat-label>
          <textarea matInput rows="2" formControlName="notes"></textarea>
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="saving() || form.invalid">
        {{ data?.id ? 'Save' : 'Create' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .form { display: flex; flex-direction: column; gap: 0.5rem; min-width: 440px; padding-top: 0.5rem; }
      .row { display: flex; gap: 0.75rem; }
      .row mat-form-field { flex: 1; }
    `,
  ],
})
export class ContactEditDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ContactService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<ContactEditDialogComponent>);
  readonly data = inject<Contact | null>(MAT_DIALOG_DATA);
  readonly saving = signal(false);
  readonly tags = signal<string[]>(this.data?.tags ?? []);

  readonly form = this.fb.nonNullable.group({
    first_name: this.fb.control<string | null>(this.data?.first_name ?? null),
    last_name: this.fb.control<string | null>(this.data?.last_name ?? null),
    mobile: this.fb.control<string | null>(this.data?.mobile_raw ?? null),
    landline: this.fb.control<string | null>(this.data?.landline_raw ?? null),
    email: this.fb.control<string | null>(this.data?.email ?? null, [Validators.email]),
    status: this.fb.nonNullable.control<string>(this.data?.status ?? 'active'),
    notes: this.fb.control<string | null>(this.data?.notes ?? null),
  });

  addTag(e: MatChipInputEvent): void {
    const v = (e.value || '').trim();
    if (v && !this.tags().includes(v)) this.tags.update((t) => [...t, v]);
    e.chipInput!.clear();
  }
  removeTag(tag: string): void { this.tags.update((t) => t.filter((x) => x !== tag)); }

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const raw = this.form.getRawValue();
    const payload = { ...raw, status: raw.status as ContactStatus, tags: this.tags() };
    const op = this.data?.id ? this.api.update(this.data.id, payload) : this.api.create(payload);
    op.subscribe({
      next: (c) => { this.notify.success(this.data?.id ? 'Contact updated.' : 'Contact created.'); this.ref.close(c); },
      error: () => this.saving.set(false),
    });
  }
}
