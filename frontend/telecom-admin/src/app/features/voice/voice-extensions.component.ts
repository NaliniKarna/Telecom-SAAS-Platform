import { Component, computed, inject, OnInit, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatChipsModule } from '@angular/material/chips';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSlideToggleModule } from '@angular/material/slide-toggle';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatTooltipModule } from '@angular/material/tooltip';
import { MatSelectModule } from '@angular/material/select';

import { VoiceService } from './voice.service';
import { AgentStatus, VoiceExtension } from './voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-extensions',
  standalone: true,
  imports: [
    DatePipe, ReactiveFormsModule,
    MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatMenuModule, MatChipsModule, MatFormFieldModule, MatInputModule,
    MatSlideToggleModule, MatProgressBarModule, MatTooltipModule,
    MatSelectModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Extensions</h1>
        <p>Manage SIP/PJSIP extensions for your company.</p>
      </div>
      @if (!formOpen()) {
        <button mat-flat-button color="primary" (click)="openCreate()">
          <mat-icon>add</mat-icon> New Extension
        </button>
      }
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (formOpen()) {
      <mat-card class="form-card">
        <mat-card-header>
          <mat-card-title>{{ editingId() ? 'Edit' : 'New' }} Extension</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <form [formGroup]="form" (ngSubmit)="save()" class="ext-form">
            <mat-form-field appearance="outline">
              <mat-label>Extension Number</mat-label>
              <input matInput formControlName="extension_number" placeholder="1001" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Display Name</mat-label>
              <input matInput formControlName="display_name" placeholder="Front Desk" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Description</mat-label>
              <input matInput formControlName="description" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Context</mat-label>
              <input matInput formControlName="context" />
            </mat-form-field>
            <mat-form-field appearance="outline">
              <mat-label>Technology</mat-label>
              <mat-select formControlName="technology">
                <mat-option value="PJSIP">PJSIP</mat-option>
                <mat-option value="SIP">SIP</mat-option>
              </mat-select>
            </mat-form-field>
            <mat-slide-toggle formControlName="enabled">Enabled</mat-slide-toggle>
            <div class="form-actions">
              <button mat-flat-button color="primary" type="submit"
                [disabled]="form.invalid || saving()">
                {{ saving() ? 'Saving...' : 'Save' }}
              </button>
              <button mat-stroked-button type="button" (click)="closeForm()">Cancel</button>
            </div>
          </form>
        </mat-card-content>
      </mat-card>
    }

    @if (extensions().length || !formOpen()) {
      <mat-card>
        <table mat-table [dataSource]="extensions()" class="full-width">
          <ng-container matColumnDef="extension_number">
            <th mat-header-cell *matHeaderCellDef>Extension</th>
            <td mat-cell *matCellDef="let e">{{ e.extension_number }}</td>
          </ng-container>
          <ng-container matColumnDef="display_name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let e">{{ e.display_name }}</td>
          </ng-container>
          <ng-container matColumnDef="technology">
            <th mat-header-cell *matHeaderCellDef>Tech</th>
            <td mat-cell *matCellDef="let e">{{ e.technology }}</td>
          </ng-container>
          <ng-container matColumnDef="assigned_user">
            <th mat-header-cell *matHeaderCellDef>Assigned To</th>
            <td mat-cell *matCellDef="let e">
              {{ e.assigned_user_name || e.assigned_user_email || '(unassigned)' }}
            </td>
          </ng-container>
          <ng-container matColumnDef="agent_status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let e">
              <mat-chip [class]="'status-' + e.agent_status"
                [matMenuTriggerFor]="statusMenu"
                [matMenuTriggerData]="{ ext: e }">
                {{ e.agent_status }}
              </mat-chip>
              <mat-menu #statusMenu="matMenu">
                @for (s of agentStatuses; track s) {
                  <button mat-menu-item (click)="setStatus(e, s)">{{ s }}</button>
                }
              </mat-menu>
            </td>
          </ng-container>
          <ng-container matColumnDef="enabled">
            <th mat-header-cell *matHeaderCellDef>Enabled</th>
            <td mat-cell *matCellDef="let e">
              <mat-icon [class]="e.enabled ? 'text-green' : 'text-red'">
                {{ e.enabled ? 'check_circle' : 'cancel' }}
              </mat-icon>
            </td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let e">
              <button mat-icon-button [matMenuTriggerFor]="actionMenu">
                <mat-icon>more_vert</mat-icon>
              </button>
              <mat-menu #actionMenu="matMenu">
                <button mat-menu-item (click)="openEdit(e)">
                  <mat-icon>edit</mat-icon> Edit
                </button>
                <button mat-menu-item (click)="toggleEnabled(e)">
                  <mat-icon>{{ e.enabled ? 'block' : 'check' }}</mat-icon>
                  {{ e.enabled ? 'Disable' : 'Enable' }}
                </button>
                <button mat-menu-item (click)="remove(e)" class="text-red">
                  <mat-icon>delete</mat-icon> Delete
                </button>
              </mat-menu>
            </td>
          </ng-container>

          <tr mat-header-row *matHeaderRowDef="columns"></tr>
          <tr mat-row *matRowDef="let row; columns: columns;"></tr>
        </table>

        @if (!loading() && extensions().length === 0) {
          <div class="empty-state">
            <mat-icon>phone_disabled</mat-icon>
            <p>No extensions registered yet.</p>
          </div>
        }
      </mat-card>
    }
  `,
  styles: [`
    .ext-form { display: flex; flex-direction: column; gap: 12px; max-width: 480px; }
    .form-card { margin-bottom: 24px; }
    .form-actions { display: flex; gap: 12px; }
    .full-width { width: 100%; }
    .empty-state { text-align: center; padding: 48px 0; color: #888; }
    .empty-state mat-icon { font-size: 48px; height: 48px; width: 48px; }
    .text-green { color: #388e3c; }
    .text-red { color: #d32f2f; }
    .status-available { background: #c8e6c9 !important; color: #1b5e20 !important; }
    .status-busy { background: #ffcdd2 !important; color: #b71c1c !important; }
    .status-away { background: #fff9c4 !important; color: #f57f17 !important; }
    .status-offline { background: #e0e0e0 !important; color: #424242 !important; }
  `],
})
export class VoiceExtensionsComponent implements OnInit {
  private readonly svc = inject(VoiceService);
  private readonly notify = inject(NotificationService);
  private readonly fb = inject(FormBuilder);

  loading = signal(true);
  saving = signal(false);
  formOpen = signal(false);
  editingId = signal<string | null>(null);
  extensions = signal<VoiceExtension[]>([]);

  agentStatuses: AgentStatus[] = ['available', 'busy', 'away', 'offline'];
  columns = [
    'extension_number', 'display_name', 'technology',
    'assigned_user', 'agent_status', 'enabled', 'actions',
  ];

  form = this.fb.group({
    extension_number: ['', [Validators.required, Validators.maxLength(20)]],
    display_name: ['', [Validators.required, Validators.maxLength(255)]],
    description: [''],
    context: ['from-internal'],
    technology: ['PJSIP'],
    enabled: [true],
  });

  ngOnInit(): void {
    this.load();
  }

  private load(): void {
    this.loading.set(true);
    this.svc.listExtensions({ limit: 200 }).subscribe({
      next: (d) => { this.extensions.set(d); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Failed to load extensions'); },
    });
  }

  openCreate(): void {
    this.editingId.set(null);
    this.form.reset({ context: 'from-internal', technology: 'PJSIP', enabled: true });
    this.form.get('extension_number')!.enable();
    this.formOpen.set(true);
  }

  openEdit(ext: VoiceExtension): void {
    this.editingId.set(ext.id);
    this.form.patchValue({
      extension_number: ext.extension_number,
      display_name: ext.display_name,
      description: ext.description || '',
      context: ext.context,
      technology: ext.technology,
      enabled: ext.enabled,
    });
    // Extension number is immutable after creation.
    this.form.get('extension_number')!.disable();
    this.formOpen.set(true);
  }

  closeForm(): void {
    this.formOpen.set(false);
    this.editingId.set(null);
  }

  save(): void {
    if (this.form.invalid) return;
    this.saving.set(true);
    const raw = this.form.getRawValue();
    const id = this.editingId();

    if (id) {
      this.svc.updateExtension(id, {
        display_name: raw.display_name!,
        description: raw.description || null,
        context: raw.context!,
        technology: raw.technology!,
        enabled: raw.enabled!,
      }).subscribe({
        next: () => { this.saving.set(false); this.closeForm(); this.load(); this.notify.success('Extension updated'); },
        error: (e) => { this.saving.set(false); this.notify.error(e?.error?.detail || 'Update failed'); },
      });
    } else {
      this.svc.createExtension({
        extension_number: raw.extension_number!,
        display_name: raw.display_name!,
        description: raw.description || undefined,
        context: raw.context!,
        technology: raw.technology!,
        enabled: raw.enabled!,
      }).subscribe({
        next: () => { this.saving.set(false); this.closeForm(); this.load(); this.notify.success('Extension created'); },
        error: (e) => { this.saving.set(false); this.notify.error(e?.error?.detail || 'Create failed'); },
      });
    }
  }

  setStatus(ext: VoiceExtension, status: AgentStatus): void {
    this.svc.updateAgentStatus(ext.id, status).subscribe({
      next: (updated) => {
        this.extensions.update(list =>
          list.map(e => e.id === updated.id ? updated : e));
      },
      error: () => this.notify.error('Failed to update status'),
    });
  }

  toggleEnabled(ext: VoiceExtension): void {
    this.svc.updateExtension(ext.id, { enabled: !ext.enabled }).subscribe({
      next: () => this.load(),
      error: () => this.notify.error('Failed to toggle extension'),
    });
  }

  remove(ext: VoiceExtension): void {
    if (!confirm(`Delete extension ${ext.extension_number}?`)) return;
    this.svc.deleteExtension(ext.id).subscribe({
      next: () => { this.load(); this.notify.success('Extension deleted'); },
      error: () => this.notify.error('Failed to delete extension'),
    });
  }
}
