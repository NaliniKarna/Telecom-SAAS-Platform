import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormsModule, FormBuilder } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AiVoiceService } from './ai-voice.service';
import { TtsPreview, Voice, VoiceTemplate } from './ai-voice.models';
import { NotificationService } from '../../core/services/notification.service';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-voice-template-preview',
  standalone: true,
  imports: [
    RouterLink, ReactiveFormsModule, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (template(); as t) {
      <header class="page-header">
        <div>
          <a routerLink="/ai-voice/templates" class="back"><mat-icon>arrow_back</mat-icon> Voice Templates</a>
          <h1>{{ t.name }}</h1>
          <p>{{ t.description || 'TTS preview — this does not send anything or start a campaign.' }}</p>
        </div>
      </header>

      <div class="layout">
        <mat-card appearance="outlined" class="panel">
          <h3>Template text</h3>
          <p class="template-text">{{ t.text }}</p>

          <h3>Voice</h3>
          <mat-form-field appearance="outline" class="full">
            <mat-label>Voice</mat-label>
            <mat-select [(ngModel)]="selectedVoiceId" [ngModelOptions]="{ standalone: true }">
              @for (v of voices(); track v.id) {
                <mat-option [value]="v.id">{{ v.name }} ({{ v.language }})</mat-option>
              }
            </mat-select>
          </mat-form-field>

          @if (t.variables.length > 0) {
            <h3>Variables</h3>
            <form [formGroup]="valuesForm" class="values-form">
              @for (name of t.variables; track name) {
                <mat-form-field appearance="outline" class="full">
                  <mat-label>{{ '{{' + name + '}}' }}</mat-label>
                  <input matInput [formControlName]="name" (input)="onValuesChange()" />
                </mat-form-field>
              }
            </form>
          } @else {
            <p class="sub">This template has no variables.</p>
          }

          <div class="actions">
            <button mat-stroked-button (click)="render()" [disabled]="rendering()">
              <mat-icon>visibility</mat-icon> Render
            </button>
            <button mat-flat-button color="primary" (click)="generate()" [disabled]="generating() || missingVars().length > 0">
              <mat-icon>graphic_eq</mat-icon> Generate TTS
            </button>
          </div>
          @if (missingVars().length > 0) {
            <p class="warn"><mat-icon>warning</mat-icon> Missing values: {{ missingVars().join(', ') }}</p>
          }
        </mat-card>

        <mat-card appearance="outlined" class="panel">
          <h3>Preview</h3>
          @if (renderedText()) {
            <p class="rendered">{{ renderedText() }}</p>
          } @else {
            <p class="sub">Render the template to see the output text here.</p>
          }

          <h3>Generated audio</h3>
          @if (generating()) {
            <mat-progress-bar mode="indeterminate" />
          }
          @if (currentPreview(); as preview) {
            <audio controls [src]="mediaUrl(preview.audio_url)" class="player"></audio>
            <div class="meta">
              <span class="tag">{{ preview.char_count }} chars</span>
              @if (preview.duration_seconds !== null) {
                <span class="tag">{{ preview.duration_seconds }}s</span>
              }
            </div>
          } @else {
            <p class="sub">Generate TTS to preview the audio here.</p>
          }
        </mat-card>
      </div>
    }
  `,
  styles: [`
    .page-header { margin-bottom: 1rem; }
    .back { display: inline-flex; align-items: center; gap: .25rem; color: var(--mat-sys-on-surface-variant); text-decoration: none; font-size: .85rem; margin-bottom: .5rem; }
    .back mat-icon { font-size: 1.1rem; height: 1.1rem; width: 1.1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); }
    .layout { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; align-items: start; }
    @media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
    .panel { padding: 1.25rem; }
    .panel h3 { margin: 0 0 .5rem; font: var(--mat-sys-title-small); }
    .panel h3:not(:first-child) { margin-top: 1.25rem; }
    .template-text { white-space: pre-wrap; background: var(--mat-sys-surface-container-low); border-radius: 8px; padding: .75rem 1rem; margin: 0; }
    .full { width: 100%; }
    .values-form { display: flex; flex-direction: column; gap: .25rem; }
    .actions { display: flex; gap: .75rem; margin-top: .75rem; }
    .warn { display: flex; align-items: center; gap: .4rem; color: var(--mat-sys-error); font-size: .82rem; margin-top: .5rem; }
    .warn mat-icon { font-size: 1.1rem; height: 1.1rem; width: 1.1rem; }
    .sub { color: var(--mat-sys-on-surface-variant); font-size: .85rem; }
    .rendered { white-space: pre-wrap; background: var(--mat-sys-surface-container-low); border-radius: 8px; padding: .75rem 1rem; }
    .player { width: 100%; margin-top: .25rem; }
    .meta { display: flex; gap: .5rem; margin-top: .5rem; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; }
  `],
})
export class VoiceTemplatePreviewComponent implements OnInit {
  private readonly route = inject(ActivatedRoute);
  private readonly api = inject(AiVoiceService);
  private readonly notify = inject(NotificationService);
  private readonly fb = inject(FormBuilder);
  // The backend returns storage paths like "/uploads/tts/...", relative to
  // its OWN origin — not the Angular dev-server origin. Left unresolved,
  // <audio src="/uploads/..."> resolves against the current page (e.g.
  // localhost:4200) instead of the API (e.g. localhost:8000), so the file
  // silently 404s and nothing plays. apiBaseUrl already ends in "/api/v1";
  // strip that to get the bare origin the upload path is actually served from.
  private readonly apiOrigin = environment.apiBaseUrl.replace(/\/api(\/v\d+)?\/?$/, '');

  mediaUrl(path: string): string {
    return /^https?:\/\//i.test(path) ? path : `${this.apiOrigin}${path}`;
  }

  readonly template = signal<VoiceTemplate | null>(null);
  readonly voices = signal<Voice[]>([]);
  readonly loading = signal(false);
  readonly rendering = signal(false);
  readonly generating = signal(false);
  readonly renderedText = signal<string | null>(null);
  readonly missingVars = signal<string[]>([]);
  readonly currentPreview = signal<TtsPreview | null>(null);

  selectedVoiceId = '';
  valuesForm = this.fb.nonNullable.group({});

  private templateId(): string {
    return this.route.snapshot.paramMap.get('id')!;
  }

  ngOnInit(): void {
    this.loading.set(true);
    const id = this.templateId();
    this.api.getTemplate(id).subscribe({
      next: (t) => {
        this.template.set(t);
        this.selectedVoiceId = t.voice_id;
        const controls: Record<string, unknown[]> = {};
        for (const name of t.variables) controls[name] = [''];
        this.valuesForm = this.fb.nonNullable.group(controls);
        this.loading.set(false);
      },
      error: () => { this.loading.set(false); this.notify.error('Unable to load voice template.'); },
    });
    this.api.listVoices({ status: 'active', size: 100 }).subscribe({
      next: (res) => this.voices.set(res.data),
      error: () => this.notify.error('Unable to load voices.'),
    });
  }

  private currentValues(): Record<string, string> {
    return this.valuesForm.getRawValue() as Record<string, string>;
  }

  onValuesChange(): void {
    // Clear stale results once the person starts editing again.
    this.renderedText.set(null);
    this.missingVars.set([]);
  }

  render(): void {
    const t = this.template();
    if (!t) return;
    this.rendering.set(true);
    this.api.renderTemplate(t.id, this.currentValues()).subscribe({
      next: (res) => {
        this.renderedText.set(res.rendered_text);
        this.missingVars.set(res.missing_variables);
        this.rendering.set(false);
      },
      error: () => { this.rendering.set(false); this.notify.error('Unable to render template.'); },
    });
  }

  generate(): void {
    const t = this.template();
    if (!t) return;
    this.generating.set(true);
    this.api.generatePreview(t.id, this.currentValues(), this.selectedVoiceId).subscribe({
      next: (preview) => {
        this.currentPreview.set(preview);
        this.renderedText.set(preview.rendered_text);
        this.missingVars.set([]);
        this.generating.set(false);
        this.notify.success('Audio generated.');
      },
      error: () => { this.generating.set(false); this.notify.error('Unable to generate audio.'); },
    });
  }
}