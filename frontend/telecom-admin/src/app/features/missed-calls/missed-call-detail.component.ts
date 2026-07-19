import { Component, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDividerModule } from '@angular/material/divider';
import { MatTooltipModule } from '@angular/material/tooltip';

import { MissedCallService } from './missed-call.service';
import { VoiceService } from '../voice/voice.service';
import { VoiceExtension } from '../voice/voice.models';
import {
  CallbackOutcome,
  MissedCallCallback,
  MissedCallDetail,
  MissedCallStatus,
} from './missed-call.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-missed-call-detail',
  standalone: true,
  imports: [
    DatePipe, FormsModule,
    MatCardModule, MatButtonModule, MatIconModule, MatChipsModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatProgressBarModule, MatDividerModule, MatTooltipModule,
  ],
  template: `
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (mc(); as m) {
      <header class="page-header">
        <div>
          <h1>Missed Call from {{ m.caller_name || m.caller_number }}</h1>
          <p>Received {{ m.received_at | date:'medium' }} on {{ m.called_extension_number || m.called_number }}</p>
        </div>
        <mat-chip [class]="'mc-status-' + m.status">{{ m.status }}</mat-chip>
      </header>

      <!-- Info card -->
      <mat-card class="info-card">
        <mat-card-content>
          <div class="info-grid">
            <div><span class="lbl">Caller</span><span>{{ m.caller_number }}</span></div>
            <div><span class="lbl">Called</span><span>{{ m.called_extension_number || m.called_number }}</span></div>
            <div><span class="lbl">Ring Duration</span><span>{{ m.ring_duration_seconds != null ? m.ring_duration_seconds + 's' : '—' }}</span></div>
            <div><span class="lbl">Callbacks</span><span>{{ m.callback_count }}</span></div>
            <div><span class="lbl">Assigned To</span><span>{{ m.assignee_name || 'Unassigned' }}</span></div>
            <div><span class="lbl">Status</span><span>{{ m.status }}</span></div>
          </div>
        </mat-card-content>
      </mat-card>

      <!-- Actions bar -->
      <div class="actions-bar">
        @if (m.status === 'new') {
          <button mat-flat-button color="accent" (click)="setStatus('acknowledged')">
            <mat-icon>visibility</mat-icon> Acknowledge
          </button>
        }
        @if (m.status !== 'closed') {
          <button mat-flat-button color="primary" (click)="showCallback = !showCallback">
            <mat-icon>phone_callback</mat-icon> Call Back
          </button>
          <button mat-stroked-button (click)="setStatus('closed')">
            <mat-icon>check_circle</mat-icon> Close
          </button>
        }
        @if (m.status === 'closed') {
          <button mat-stroked-button (click)="setStatus('new')">
            <mat-icon>replay</mat-icon> Reopen
          </button>
        }
      </div>

      <!-- Callback form -->
      @if (showCallback) {
        <mat-card class="callback-card">
          <mat-card-header><mat-card-title>Initiate Callback</mat-card-title></mat-card-header>
          <mat-card-content>
            <div class="cb-form">
              <mat-form-field appearance="outline">
                <mat-label>Your Extension</mat-label>
                <mat-select [(ngModel)]="cbExtensionId">
                  <mat-option [value]="null">Manual number</mat-option>
                  @for (ext of extensions(); track ext.id) {
                    <mat-option [value]="ext.id">{{ ext.extension_number }} — {{ ext.display_name }}</mat-option>
                  }
                </mat-select>
              </mat-form-field>
              @if (!cbExtensionId) {
                <mat-form-field appearance="outline">
                  <mat-label>Caller Number</mat-label>
                  <input matInput [(ngModel)]="cbCallerNumber" />
                </mat-form-field>
              }
              <mat-form-field appearance="outline">
                <mat-label>Notes</mat-label>
                <textarea matInput [(ngModel)]="cbNotes" rows="2"></textarea>
              </mat-form-field>
              <button mat-flat-button color="primary" (click)="doCallback()" [disabled]="calling()">
                {{ calling() ? 'Dialing...' : 'Dial ' + m.caller_number }}
              </button>
            </div>
          </mat-card-content>
        </mat-card>
      }

      <!-- Callback history -->
      @if (m.callbacks.length) {
        <h2 class="section-heading">Callback History</h2>
        @for (cb of m.callbacks; track cb.id) {
          <mat-card class="cb-row">
            <mat-card-content>
              <div class="cb-header">
                <strong>{{ cb.performer_name }}</strong>
                <span class="muted">{{ cb.attempted_at | date:'short' }}</span>
                @if (cb.outcome) {
                  <mat-chip [class]="'cb-outcome-' + cb.outcome">{{ cb.outcome }}</mat-chip>
                } @else {
                  <div class="outcome-form">
                    <mat-form-field appearance="outline" class="sm-field">
                      <mat-select [(ngModel)]="pendingOutcomes[cb.id]" placeholder="Outcome">
                        @for (o of outcomes; track o) {
                          <mat-option [value]="o">{{ o }}</mat-option>
                        }
                      </mat-select>
                    </mat-form-field>
                    <button mat-stroked-button (click)="saveOutcome(cb)"
                      [disabled]="!pendingOutcomes[cb.id]">Save</button>
                  </div>
                }
              </div>
              @if (cb.extension_number) { <div class="muted">Ext: {{ cb.extension_number }}</div> }
              @if (cb.duration_seconds != null) { <div class="muted">Duration: {{ cb.duration_seconds }}s</div> }
              @if (cb.notes) { <div class="cb-note">{{ cb.notes }}</div> }
            </mat-card-content>
          </mat-card>
        }
      }

      <mat-divider />

      <!-- Notes -->
      <h2 class="section-heading">Notes</h2>
      @for (n of m.notes; track n.id) {
        <mat-card class="note-card">
          <mat-card-content>
            <div class="note-header">
              <strong>{{ n.author_name }}</strong>
              <span class="muted">{{ n.created_at | date:'short' }}</span>
            </div>
            <p>{{ n.body }}</p>
          </mat-card-content>
        </mat-card>
      }
      <div class="note-form">
        <mat-form-field appearance="outline" class="note-input">
          <mat-label>Add a note</mat-label>
          <textarea matInput [(ngModel)]="noteBody" rows="2"></textarea>
        </mat-form-field>
        <button mat-flat-button color="primary" (click)="addNote()"
          [disabled]="!noteBody.trim()">Add Note</button>
      </div>
    }
  `,
  styles: [`
    .info-card { margin-bottom: 16px; }
    .info-grid {
      display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
      gap: 12px;
    }
    .info-grid .lbl { display: block; font-size: 12px; color: #888; margin-bottom: 2px; }
    .actions-bar { display: flex; gap: 12px; margin-bottom: 24px; }
    .callback-card { margin-bottom: 24px; }
    .cb-form { display: flex; flex-direction: column; gap: 12px; max-width: 420px; }
    .section-heading { margin: 16px 0 12px; font-size: 18px; font-weight: 600; }
    .cb-row { margin-bottom: 8px; }
    .cb-header { display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
    .muted { font-size: 12px; color: #888; }
    .cb-note { margin-top: 6px; font-style: italic; color: #555; }
    .outcome-form { display: flex; gap: 8px; align-items: center; }
    .sm-field { width: 140px; }
    .note-card { margin-bottom: 8px; }
    .note-header { display: flex; gap: 12px; align-items: center; margin-bottom: 4px; }
    .note-form { display: flex; gap: 12px; align-items: flex-start; margin-top: 8px; }
    .note-input { flex: 1; }
    .mc-status-new { background: #fff3e0 !important; color: #e65100 !important; }
    .mc-status-acknowledged { background: #fff9c4 !important; color: #f57f17 !important; }
    .mc-status-returned { background: #e3f2fd !important; color: #1565c0 !important; }
    .mc-status-closed { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .cb-outcome-answered { background: #e8f5e9 !important; color: #2e7d32 !important; }
    .cb-outcome-no_answer { background: #fce4ec !important; color: #880e4f !important; }
    .cb-outcome-busy { background: #fff3e0 !important; color: #e65100 !important; }
    .cb-outcome-voicemail { background: #e3f2fd !important; color: #1565c0 !important; }
    .cb-outcome-failed { background: #ffebee !important; color: #c62828 !important; }
  `],
})
export class MissedCallDetailComponent implements OnInit {
  private readonly svc = inject(MissedCallService);
  private readonly voiceSvc = inject(VoiceService);
  private readonly route = inject(ActivatedRoute);
  private readonly notify = inject(NotificationService);

  loading = signal(true);
  calling = signal(false);
  mc = signal<MissedCallDetail | null>(null);
  extensions = signal<VoiceExtension[]>([]);

  showCallback = false;
  cbExtensionId: string | null = null;
  cbCallerNumber = '';
  cbNotes = '';
  noteBody = '';
  pendingOutcomes: Record<string, string> = {};
  outcomes: CallbackOutcome[] = ['answered', 'no_answer', 'busy', 'voicemail', 'failed'];

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id')!;
    this.loadDetail(id);
    this.voiceSvc.listExtensions({ limit: 200 }).subscribe({
      next: (d) => this.extensions.set(d.filter((e) => e.enabled)),
    });
  }

  private loadDetail(id: string): void {
    this.loading.set(true);
    this.svc.get(id).subscribe({
      next: (d) => { this.mc.set(d); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Failed to load missed call'); },
    });
  }

  setStatus(status: string): void {
    const id = this.mc()!.id;
    this.svc.updateStatus(id, status).subscribe({
      next: () => { this.loadDetail(id); this.notify.success(`Status updated to ${status}`); },
      error: () => this.notify.error('Status update failed'),
    });
  }

  doCallback(): void {
    const m = this.mc()!;
    if (!this.cbExtensionId && !this.cbCallerNumber) {
      this.notify.error('Select an extension or enter a caller number.');
      return;
    }
    this.calling.set(true);
    this.svc.initiateCallback(m.id, {
      extension_id: this.cbExtensionId || undefined,
      caller_number: this.cbExtensionId ? undefined : (this.cbCallerNumber || undefined),
      notes: this.cbNotes || undefined,
    }).subscribe({
      next: () => {
        this.calling.set(false);
        this.showCallback = false;
        this.cbNotes = '';
        this.loadDetail(m.id);
        this.notify.success('Callback initiated');
      },
      error: (e) => {
        this.calling.set(false);
        this.notify.error(e?.error?.detail || 'Callback failed');
      },
    });
  }

  saveOutcome(cb: MissedCallCallback): void {
    const outcome = this.pendingOutcomes[cb.id];
    if (!outcome) return;
    this.svc.updateCallbackOutcome(cb.missed_call_id, cb.id, outcome).subscribe({
      next: () => { this.loadDetail(cb.missed_call_id); this.notify.success('Outcome saved'); },
      error: () => this.notify.error('Failed to save outcome'),
    });
  }

  addNote(): void {
    const id = this.mc()!.id;
    this.svc.addNote(id, this.noteBody.trim()).subscribe({
      next: () => { this.noteBody = ''; this.loadDetail(id); this.notify.success('Note added'); },
      error: () => this.notify.error('Failed to add note'),
    });
  }
}
