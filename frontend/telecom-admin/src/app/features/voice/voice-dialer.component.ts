import { Component, inject, OnInit, signal } from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { Router } from '@angular/router';

import { VoiceService } from './voice.service';
import { VoiceExtension, VoiceCallLog } from './voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-dialer',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    MatCardModule, MatButtonModule, MatIconModule,
    MatFormFieldModule, MatInputModule, MatSelectModule,
    MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Dialer</h1>
        <p>Initiate an outbound call. Select your extension, enter a destination, and dial.</p>
      </div>
    </header>

    <mat-card class="dialer-card">
      <mat-card-content>
        <form [formGroup]="form" (ngSubmit)="dial()" class="dialer-form">
          <mat-form-field appearance="outline">
            <mat-label>Your Extension (A-leg)</mat-label>
            <mat-select formControlName="caller_extension_id">
              <mat-option [value]="null">Manual number below</mat-option>
              @for (ext of extensions(); track ext.id) {
                <mat-option [value]="ext.id">
                  {{ ext.extension_number }} &mdash; {{ ext.display_name }}
                </mat-option>
              }
            </mat-select>
          </mat-form-field>

          @if (!form.value.caller_extension_id) {
            <mat-form-field appearance="outline">
              <mat-label>Caller Number</mat-label>
              <input matInput formControlName="caller_number" placeholder="9801234567" />
            </mat-form-field>
          }

          <mat-form-field appearance="outline" class="destination-field">
            <mat-label>Destination Number</mat-label>
            <input matInput formControlName="destination_number" placeholder="9807654321" />
            <mat-icon matPrefix>dialpad</mat-icon>
          </mat-form-field>

          <mat-form-field appearance="outline">
            <mat-label>Caller ID Override (optional)</mat-label>
            <input matInput formControlName="caller_id_override" />
          </mat-form-field>

          <button mat-fab extended color="primary" type="submit"
            [disabled]="form.invalid || calling()" class="dial-button">
            <mat-icon>call</mat-icon>
            {{ calling() ? 'Dialing...' : 'Dial' }}
          </button>
        </form>

        @if (calling()) { <mat-progress-bar mode="indeterminate" /> }

        @if (lastCall(); as c) {
          <div class="last-call">
            <mat-icon class="call-icon success">call_made</mat-icon>
            <div>
              <strong>Call initiated</strong>
              <p>{{ c.caller_number }} &rarr; {{ c.callee_number }}</p>
              <p class="muted">Status: {{ c.status }} &middot; Action ID: {{ c.action_id }}</p>
            </div>
          </div>
        }
      </mat-card-content>
    </mat-card>
  `,
  styles: [`
    .dialer-card { max-width: 520px; }
    .dialer-form {
      display: flex;
      flex-direction: column;
      gap: 12px;
    }
    .destination-field input { font-size: 20px; letter-spacing: 2px; }
    .dial-button { align-self: flex-start; margin-top: 8px; }
    .last-call {
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-top: 24px;
      padding: 16px;
      border-radius: 8px;
      background: #e8f5e9;
    }
    .call-icon.success { color: #388e3c; font-size: 32px; width: 32px; height: 32px; }
    .muted { color: #666; font-size: 13px; margin-top: 4px; }
  `],
})
export class VoiceDialerComponent implements OnInit {
  private readonly svc = inject(VoiceService);
  private readonly notify = inject(NotificationService);
  private readonly fb = inject(FormBuilder);
  private readonly router = inject(Router);

  extensions = signal<VoiceExtension[]>([]);
  calling = signal(false);
  lastCall = signal<VoiceCallLog | null>(null);

  form = this.fb.group({
    caller_extension_id: [null as string | null],
    caller_number: [''],
    destination_number: ['', [Validators.required]],
    caller_id_override: [''],
  });

  ngOnInit(): void {
    this.svc.listExtensions({ limit: 200 }).subscribe({
      next: (d) => this.extensions.set(d.filter(e => e.enabled)),
    });
  }

  dial(): void {
    if (this.form.invalid) return;
    const v = this.form.value;

    if (!v.caller_extension_id && !v.caller_number) {
      this.notify.error('Select an extension or enter a caller number.');
      return;
    }

    this.calling.set(true);
    this.svc.originateCall({
      caller_extension_id: v.caller_extension_id || undefined,
      caller_number: v.caller_extension_id ? undefined : (v.caller_number || undefined),
      destination_number: v.destination_number!,
      caller_id_override: v.caller_id_override || undefined,
    }).subscribe({
      next: (call) => {
        this.calling.set(false);
        this.lastCall.set(call);
        this.notify.success('Call initiated');
      },
      error: (e) => {
        this.calling.set(false);
        this.notify.error(e?.error?.detail || 'Call failed');
      },
    });
  }
}
