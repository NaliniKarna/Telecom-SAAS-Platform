import { Component, inject, signal } from '@angular/core';
import { Router, ActivatedRoute, RouterLink } from '@angular/router';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { VoiceCampaignService } from './voice-campaign.service';
import { VoiceCampaignEstimate } from './voice-campaign.models';
import { ContactListService } from '../contacts/contact-list.service';
import { ContactGroup } from '../contacts/contact.models';
import { AiVoiceService } from '../ai-voice/ai-voice.service';
import { Voice, VoiceTemplate } from '../ai-voice/ai-voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-campaign-form',
  standalone: true,
  imports: [
    RouterLink, ReactiveFormsModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatIconModule, MatProgressBarModule,
  ],
  template: `
    <a mat-button routerLink="/voice-campaigns"><mat-icon>arrow_back</mat-icon> Voice Campaigns</a>
    <header class="page-header"><h1>{{ editing ? 'Edit draft' : 'New voice campaign' }}</h1></header>
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    <div class="layout">
      <mat-card appearance="outlined" class="form-card">
        <form [formGroup]="form" class="form">
          <mat-form-field appearance="outline">
            <mat-label>Campaign name</mat-label>
            <input matInput formControlName="name" />
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Contact list</mat-label>
            <mat-select formControlName="contact_list_id" (selectionChange)="refreshEstimate()">
              @for (l of lists(); track l.id) {
                <mat-option [value]="l.id">{{ l.name }}</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Voice template</mat-label>
            <mat-select formControlName="voice_template_id" (selectionChange)="refreshEstimate()">
              @for (t of templates(); track t.id) {
                <mat-option [value]="t.id">{{ t.name }}</mat-option>
              }
            </mat-select>
            <mat-hint>The template's own voice is used unless overridden below.</mat-hint>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Voice override (optional)</mat-label>
            <mat-select formControlName="voice_id" (selectionChange)="refreshEstimate()">
              <mat-option [value]="null">Use template's voice</mat-option>
              @for (v of voices(); track v.id) {
                <mat-option [value]="v.id">{{ v.name }} ({{ v.language }})</mat-option>
              }
            </mat-select>
          </mat-form-field>

          <div class="actions">
            <button mat-button type="button" routerLink="/voice-campaigns">Cancel</button>
            <button mat-flat-button color="primary" type="button" (click)="submit()" [disabled]="saving() || form.invalid">
              {{ editing ? 'Save draft' : 'Create draft' }}
            </button>
          </div>
        </form>
      </mat-card>

      <mat-card appearance="outlined" class="estimate-card">
        <h3><mat-icon>calculate</mat-icon> Before you start</h3>
        @if (!estimate() && editing) { <p class="muted">Loading estimate…</p> }
        @if (!editing) { <p class="muted">Save this as a draft first to see recipient count and quota impact.</p> }
        @if (estimate(); as e) {
          <div class="stat"><span class="k">Recipients</span><span class="v">{{ e.recipient_count }}</span></div>
          <div class="stat"><span class="k">Estimated characters</span><span class="v">{{ e.estimated_characters }}</span></div>
          <div class="stat">
            <span class="k">Available quota</span>
            <span class="v">
              @if (e.usage.available_characters !== null) { {{ e.usage.available_characters }} }
              @else { Unlimited }
            </span>
          </div>
          @if (e.errors.length > 0) {
            <div class="errors">
              @for (err of e.errors; track err) { <div class="error-line"><mat-icon>error</mat-icon> {{ err }}</div> }
            </div>
          }
          @if (e.can_start) {
            <button mat-flat-button color="primary" class="start-btn" (click)="start()" [disabled]="starting()">
              <mat-icon>play_arrow</mat-icon> Start campaign
            </button>
          }
        }
      </mat-card>
    </div>
  `,
  styles: [`
    .page-header h1 { margin: .5rem 0 1rem; }
    .layout { display: flex; gap: 1.5rem; flex-wrap: wrap; align-items: flex-start; }
    .form-card { flex: 1 1 480px; max-width: 640px; }
    .estimate-card { flex: 1 1 320px; max-width: 380px; padding: 1rem; }
    .estimate-card h3 { display: flex; align-items: center; gap: .4rem; margin: 0 0 1rem; font-size: 1rem; }
    .form { display: flex; flex-direction: column; gap: .5rem; padding-top: .5rem; }
    .actions { display: flex; justify-content: flex-end; gap: .5rem; margin-top: 1rem; }
    .muted { color: var(--mat-sys-on-surface-variant); }
    .stat { display: flex; justify-content: space-between; padding: .4rem 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
    .stat .k { color: var(--mat-sys-on-surface-variant); } .stat .v { font-weight: 600; }
    .errors { margin-top: 1rem; display: flex; flex-direction: column; gap: .4rem; }
    .error-line { display: flex; align-items: flex-start; gap: .4rem; color: var(--mat-sys-error); font-size: .82rem; }
    .error-line mat-icon { font-size: 1.1rem; height: 1.1rem; width: 1.1rem; margin-top: .1rem; }
    .start-btn { width: 100%; margin-top: 1rem; }
  `],
})
export class VoiceCampaignFormComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(VoiceCampaignService);
  private readonly listsApi = inject(ContactListService);
  private readonly aiVoiceApi = inject(AiVoiceService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  readonly saving = signal(false);
  readonly starting = signal(false);
  readonly loading = signal(false);
  readonly lists = signal<ContactGroup[]>([]);
  readonly templates = signal<VoiceTemplate[]>([]);
  readonly voices = signal<Voice[]>([]);
  readonly estimate = signal<VoiceCampaignEstimate | null>(null);
  readonly editing: boolean;
  private id: string | null;

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    contact_list_id: ['', [Validators.required]],
    voice_template_id: ['', [Validators.required]],
    voice_id: this.fb.control<string | null>(null),
  });

  constructor() {
    this.id = this.route.snapshot.paramMap.get('id');
    this.editing = !!this.id;
    this.listsApi.list('', 1, 100).subscribe((r) => this.lists.set(r.data));
    this.aiVoiceApi.listTemplates({ status: 'active', size: 100 }).subscribe((r) => this.templates.set(r.data));
    this.aiVoiceApi.listVoices({ status: 'active', size: 100 }).subscribe((r) => this.voices.set(r.data));
    if (this.editing && this.id) this.loadCampaign(this.id);
  }

  loadCampaign(id: string): void {
    this.loading.set(true);
    this.api.getCampaign(id).subscribe({
      next: (c) => {
        this.form.patchValue({
          name: c.name,
          contact_list_id: c.contact_list_id ?? '',
          voice_template_id: c.voice_template_id ?? '',
          voice_id: c.voice_id,
        });
        this.loading.set(false);
        this.refreshEstimate();
      },
      error: () => { this.loading.set(false); this.notify.error('Unable to load campaign.'); },
    });
  }

  refreshEstimate(): void {
    if (!this.id) return;
    this.api.estimate(this.id).subscribe({
      next: (e) => this.estimate.set(e),
      error: () => this.notify.error('Unable to load campaign estimate.'),
    });
  }

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    const v = this.form.getRawValue();
    this.saving.set(true);
    const payload = {
      name: v.name, contact_list_id: v.contact_list_id,
      voice_template_id: v.voice_template_id, voice_id: v.voice_id,
    };
    const done = {
      next: (c: { id: string }) => {
        this.notify.success('Campaign saved.');
        this.router.navigate(['/voice-campaigns', c.id, 'edit']).then(() => {
          this.id = c.id;
          this.refreshEstimate();
        });
      },
      error: (err: { error?: { errors?: { message?: string }[] } }) => {
        this.saving.set(false);
        this.notify.error(err?.error?.errors?.[0]?.message ?? 'Unable to save campaign.');
      },
    };
    if (this.editing && this.id) this.api.updateCampaign(this.id, payload).subscribe({ ...done, next: () => { this.notify.success('Draft saved.'); this.saving.set(false); this.refreshEstimate(); } });
    else this.api.createCampaign(payload).subscribe(done);
  }

  start(): void {
    if (!this.id || this.starting()) return;
    this.starting.set(true);
    this.api.startCampaign(this.id).subscribe({
      next: () => { this.notify.success('Campaign started.'); this.router.navigate(['/voice-campaigns', this.id]); },
      error: (err: { error?: { errors?: { message?: string }[] } }) => {
        this.starting.set(false);
        this.notify.error(err?.error?.errors?.[0]?.message ?? 'Unable to start campaign.');
      },
    });
  }
}
