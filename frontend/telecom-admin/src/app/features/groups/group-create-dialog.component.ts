import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';

import { GroupService } from './group.service';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-group-create-dialog',
  standalone: true,
  imports: [ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatSelectModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>New group</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" />
          @if (form.controls.name.hasError('required') && form.controls.name.touched) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Description</mat-label>
          <textarea matInput rows="2" formControlName="description"></textarea>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Type</mat-label>
          <mat-select formControlName="group_type">
            <mat-option value="internal">Internal (users)</mat-option>
          </mat-select>
        </mat-form-field>
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
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="saving() || form.invalid">Create</button>
    </mat-dialog-actions>
  `,
  styles: [`.form { display: flex; flex-direction: column; gap: 0.5rem; min-width: 360px; padding-top: 0.5rem; }`],
})
export class GroupCreateDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(GroupService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<GroupCreateDialogComponent>);
  readonly saving = signal(false);

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    description: this.fb.control<string | null>(null),
    group_type: this.fb.nonNullable.control<'internal'>('internal'),
    status: this.fb.nonNullable.control<'active' | 'inactive'>('active'),
  });

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    this.api.create(this.form.getRawValue()).subscribe({
      next: (g) => { this.notify.success('Group created.'); this.ref.close(g); },
      error: () => this.saving.set(false),
    });
  }
}
