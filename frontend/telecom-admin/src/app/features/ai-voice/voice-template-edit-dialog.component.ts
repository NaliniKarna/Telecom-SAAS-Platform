import { Component, inject, OnInit, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef, MAT_DIALOG_DATA } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { AiVoiceService } from './ai-voice.service';
import { Voice, VoiceTemplate } from './ai-voice.models';
import { NotificationService } from '../../core/services/notification.service';

const LANGUAGES = [
  { value: 'ne', label: 'Nepali' },
  { value: 'en', label: 'English' },
];

@Component({
  selector: 'app-voice-template-edit-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatProgressSpinnerModule,
  ],
  template: `
    <h2 mat-dialog-title>{{ editing ? 'Edit voice template' : 'New voice template' }}</h2>
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
          <mat-label>Description (optional)</mat-label>
          <input matInput formControlName="description" />
        </mat-form-field>

        <div class="row">
          <mat-form-field appearance="outline" class="lang">
            <mat-label>Language</mat-label>
            <mat-select formControlName="language">
              @for (l of languages; track l.value) { <mat-option [value]="l.value">{{ l.label }}</mat-option> }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline" class="voice">
            <mat-label>Voice</mat-label>
            @if (loadingVoices()) {
              <mat-spinner matSuffix diameter="18" />
            }
            <mat-select formControlName="voice_id">
              @for (v of voices(); track v.id) {
                <mat-option [value]="v.id">{{ v.name }} ({{ v.language }})</mat-option>
              }
            </mat-select>
            @if (form.controls.voice_id.hasError('required') && form.controls.voice_id.touched) {
              <mat-error>Select a voice.</mat-error>
            }
          </mat-form-field>
        </div>

        <mat-form-field appearance="outline">
          <mat-label>Text</mat-label>
          <textarea matInput rows="4" formControlName="text" (input)="onTextChange()"></textarea>
          <mat-hint>Insert placeholders like {{ '{{name}}' }}.</mat-hint>
          @if (form.controls.text.hasError('required') && form.controls.text.touched) {
            <mat-error>Text is required.</mat-error>
          }
        </mat-form-field>

        @if (detectedVars().length > 0) {
          <div class="detected">
            <span class="label">Detected variables:</span>
            @for (v of detectedVars(); track v) { <span class="tag">{{ v }}</span> }
          </div>
        }

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
    .form { display: flex; flex-direction: column; gap: .5rem; min-width: 460px; padding-top: .5rem; }
    .row { display: flex; gap: .75rem; }
    .row .lang { flex: 1 1 140px; } .row .voice { flex: 2 1 260px; }
    .detected { margin: -.25rem 0 .25rem; display: flex; align-items: center; gap: .4rem; flex-wrap: wrap; }
    .detected .label { color: var(--mat-sys-on-surface-variant); font-size: .8rem; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .75rem; font-family: monospace; }
  `],
})
export class VoiceTemplateEditDialogComponent implements OnInit {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(AiVoiceService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<VoiceTemplateEditDialogComponent>);
  readonly data = inject<{ template?: VoiceTemplate }>(MAT_DIALOG_DATA, { optional: true });
  readonly saving = signal(false);
  readonly editing = !!this.data?.template;
  readonly languages = LANGUAGES;
  readonly voices = signal<Voice[]>([]);
  readonly loadingVoices = signal(false);
  readonly detectedVars = signal<string[]>(this.data?.template?.variables ?? []);

  readonly form = this.fb.nonNullable.group({
    name: [this.data?.template?.name ?? '', [Validators.required]],
    description: [this.data?.template?.description ?? ''],
    language: this.fb.nonNullable.control(this.data?.template?.language ?? 'ne'),
    voice_id: [this.data?.template?.voice_id ?? '', [Validators.required]],
    text: [this.data?.template?.text ?? '', [Validators.required]],
    status: this.fb.nonNullable.control<'active' | 'inactive'>(this.data?.template?.status ?? 'active'),
  });

  ngOnInit(): void {
    this.loadingVoices.set(true);
    this.api.listVoices({ status: 'active', size: 100 }).subscribe({
      next: (res) => { this.voices.set(res.data); this.loadingVoices.set(false); },
      error: () => { this.loadingVoices.set(false); this.notify.error('Unable to load voices.'); },
    });
  }

  onTextChange(): void {
    const text = this.form.controls.text.value;
    this.detectedVars.set([...new Set([...text.matchAll(/\{\{\s*([a-zA-Z0-9_]+)\s*\}\}/g)].map((m) => m[1]))]);
  }

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const v = this.form.getRawValue();
    const done = {
      next: (t: VoiceTemplate) => { this.notify.success(this.editing ? 'Voice template updated.' : 'Voice template created.'); this.ref.close(t); },
      error: () => this.saving.set(false),
    };
    if (this.editing) {
      this.api.updateTemplate(this.data!.template!.id, v).subscribe(done);
    } else {
      this.api.createTemplate(v).subscribe(done);
    }
  }
}
