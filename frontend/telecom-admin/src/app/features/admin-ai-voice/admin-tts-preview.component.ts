import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AdminAiVoiceService } from './admin-ai-voice.service';
import { AdminTtsPreviewResponse, AdminVoice } from './admin-ai-voice.models';
import { NotificationService } from '../../core/services/notification.service';
import { environment } from '../../../environments/environment';

@Component({
  selector: 'app-admin-tts-preview',
  standalone: true,
  imports: [
    RouterLink, FormsModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <a routerLink="/admin/ai-voice/voices" class="back"><mat-icon>arrow_back</mat-icon> Voices</a>
        <h1>Test a voice</h1>
        <p>Quick smoke test of any platform voice. Not tied to a company or template — nothing is saved except an audit entry.</p>
      </div>
    </header>

    <mat-card appearance="outlined" class="panel">
      <mat-form-field appearance="outline" class="full">
        <mat-label>Voice</mat-label>
        <mat-select [(ngModel)]="voiceId">
          @for (v of voices(); track v.id) {
            <mat-option [value]="v.id">{{ v.name }} ({{ v.language }}) — {{ v.status }}</mat-option>
          }
        </mat-select>
      </mat-form-field>

      <mat-form-field appearance="outline" class="full">
        <mat-label>Text</mat-label>
        <textarea matInput rows="4" [(ngModel)]="text" placeholder="Type anything to test this voice..."></textarea>
      </mat-form-field>

      <button mat-flat-button color="primary" (click)="generate()" [disabled]="generating() || !voiceId || !text.trim()">
        <mat-icon>graphic_eq</mat-icon> Generate
      </button>

      @if (generating()) { <mat-progress-bar mode="indeterminate" /> }

      @if (result(); as r) {
        <div class="result">
          <audio controls [src]="mediaUrl(r.audio_url)" class="player"></audio>
          <div class="meta">
            <span class="tag">{{ r.char_count }} chars</span>
            @if (r.duration_seconds !== null) { <span class="tag">{{ r.duration_seconds }}s</span> }
          </div>
        </div>
      }
    </mat-card>
  `,
  styles: [`
    .page-header { margin-bottom: 1rem; }
    .back { display: inline-flex; align-items: center; gap: .25rem; color: var(--mat-sys-on-surface-variant); text-decoration: none; font-size: .85rem; margin-bottom: .5rem; }
    .back mat-icon { font-size: 1.1rem; height: 1.1rem; width: 1.1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); max-width: 560px; }
    .panel { padding: 1.25rem; max-width: 560px; display: flex; flex-direction: column; gap: .75rem; }
    .full { width: 100%; }
    .result { margin-top: .5rem; }
    .player { width: 100%; }
    .meta { display: flex; gap: .5rem; margin-top: .5rem; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; }
  `],
})
export class AdminTtsPreviewComponent implements OnInit {
  private readonly api = inject(AdminAiVoiceService);
  private readonly notify = inject(NotificationService);
  private readonly apiOrigin = environment.apiBaseUrl.replace(/\/api(\/v\d+)?\/?$/, '');

  readonly voices = signal<AdminVoice[]>([]);
  readonly generating = signal(false);
  readonly result = signal<AdminTtsPreviewResponse | null>(null);
  voiceId = '';
  text = '';

  ngOnInit(): void {
    this.api.listVoices({ status: 'active', size: 100 }).subscribe({
      next: (res) => { this.voices.set(res.data); if (res.data.length) this.voiceId = res.data[0].id; },
      error: () => this.notify.error('Unable to load voices.'),
    });
  }

  mediaUrl(path: string): string {
    return /^https?:\/\//i.test(path) ? path : `${this.apiOrigin}${path}`;
  }

  generate(): void {
    if (!this.voiceId || !this.text.trim()) return;
    this.generating.set(true);
    this.api.generatePreview({ text: this.text, voice_id: this.voiceId }).subscribe({
      next: (res) => { this.result.set(res); this.generating.set(false); this.notify.success('Audio generated.'); },
      error: () => { this.generating.set(false); this.notify.error('Unable to generate audio.'); },
    });
  }
}
