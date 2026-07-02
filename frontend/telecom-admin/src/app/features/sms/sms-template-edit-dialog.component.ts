import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';

import { SmsService } from './sms.service';
import { SmsTemplate } from './sms.models';
import { NotificationService } from '../../core/services/notification.service';

const KNOWN_VARS = ['name', 'phone', 'company'];

@Component({
  selector: 'app-sms-template-edit-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatChipsModule, MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ editing ? 'Edit template' : 'New template' }}</h2>
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
          <mat-label>Message body</mat-label>
          <textarea matInput rows="4" formControlName="body" (input)="onBodyChange()"></textarea>
          <mat-hint>{{ hint }}</mat-hint>
          @if (form.controls.body.hasError('required') && form.controls.body.touched) {
            <mat-error>Body is required.</mat-error>
          }
        </mat-form-field>

        <div class="vars">
          <span class="label">Insert variable:</span>
          @for (v of knownVars; track v) {
            <button type="button" mat-stroked-button class="chip-btn" (click)="insertVar(v)">{{ varLabel(v) }}</button>
          }
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Status</mat-label>
          <mat-select formControlName="status">
            <mat-option value="active">Active</mat-option>
            <mat-option value="inactive">Inactive</mat-option>
          </mat-select>
        </mat-form-field>

        <div class="preview">
          <div class="preview-head"><mat-icon>visibility</mat-icon> Preview</div>
          <p class="preview-body">{{ preview() || 'Start typing to see a preview…' }}</p>
          @if (detectedVars().length > 0) {
            <div class="detected">
              <span class="label">Detected variables:</span>
              @for (v of detectedVars(); track v) { <span class="tag">{{ v }}</span> }
            </div>
          }
        </div>
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
    .form { display: flex; flex-direction: column; gap: .5rem; min-width: 460px; padding-top: .5rem; }
    .vars { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; margin: -.25rem 0 .25rem; }
    .vars .label, .detected .label { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .chip-btn { min-width: auto; padding: 0 .6rem; line-height: 1.8rem; font-family: monospace; }
    .preview { border: 1px dashed var(--mat-sys-outline-variant); border-radius: 12px; padding: .75rem 1rem; background: var(--mat-sys-surface-container-low); }
    .preview-head { display: flex; align-items: center; gap: .4rem; font-size: .8rem; color: var(--mat-sys-on-surface-variant); margin-bottom: .4rem; }
    .preview-head mat-icon { font-size: 1rem; height: 1rem; width: 1rem; }
    .preview-body { margin: 0; white-space: pre-wrap; }
    .detected { margin-top: .6rem; display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .75rem; font-family: monospace; }
  `],
})
export class SmsTemplateEditDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(SmsService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<SmsTemplateEditDialogComponent>);
  readonly data = inject<{ template?: SmsTemplate }>(MAT_DIALOG_DATA, { optional: true });
  readonly saving = signal(false);
  readonly editing = !!this.data?.template;
  readonly knownVars = KNOWN_VARS;
  readonly hint = 'Insert placeholders like {{name}}.';
  varLabel(v: string): string { return `{{${v}}}`; }
  readonly preview = signal('');
  readonly detectedVars = signal<string[]>([]);

  // Sample values for the live preview (matches backend KNOWN_VARIABLES).
  private readonly sample: Record<string, string> = { name: 'Aarav Sharma', phone: '+9779812345678', company: 'Acme Pvt. Ltd.' };

  readonly form = this.fb.nonNullable.group({
    name: [this.data?.template?.name ?? '', [Validators.required]],
    body: [this.data?.template?.body ?? '', [Validators.required]],
    status: this.fb.nonNullable.control<'active' | 'inactive'>(this.data?.template?.status ?? 'active'),
  });

  constructor() { if (this.editing) this.onBodyChange(); }

  onBodyChange(): void {
    const body = this.form.controls.body.value;
    // Local render mirrors the backend: known vars substituted, unknown left intact.
    this.detectedVars.set([...new Set([...body.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)].map((m) => m[1]))]);
    this.preview.set(body.replace(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g, (full, k) => this.sample[k] ?? full));
  }

  insertVar(v: string): void {
    const ctrl = this.form.controls.body;
    ctrl.setValue(`${ctrl.value}{{${v}}}`);
    this.onBodyChange();
  }

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const v = this.form.getRawValue();
    const done = {
      next: (t: SmsTemplate) => { this.notify.success(this.editing ? 'Template updated.' : 'Template created.'); this.ref.close(t); },
      error: () => this.saving.set(false),
    };
    if (this.editing) {
      this.api.updateTemplate(this.data!.template!.id, v).subscribe(done);
    } else {
      this.api.createTemplate(v).subscribe(done);
    }
  }
}
