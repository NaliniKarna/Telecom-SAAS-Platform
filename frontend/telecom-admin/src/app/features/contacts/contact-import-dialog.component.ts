import { Component, inject, signal, computed } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTableModule } from '@angular/material/table';
import { MatRadioModule } from '@angular/material/radio';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { ContactService } from './contact.service';
import {
  ImportCommitRow, ImportPreview, ImportResult, ImportRowResult,
} from './contact.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-contact-import-dialog',
  standalone: true,
  imports: [
    FormsModule, MatDialogModule, MatButtonModule, MatIconModule,
    MatTableModule, MatRadioModule, MatProgressBarModule,
  ],
  template: `
    <h2 mat-dialog-title>Import contacts from CSV</h2>
    <mat-dialog-content>
      @if (busy()) { <mat-progress-bar mode="indeterminate" /> }

      <!-- Step 1: upload -->
      @if (step() === 'upload') {
        <div class="upload">
          <p class="hint">
            CSV columns: first_name, last_name, mobile, landline, email, tags, notes, status.
            At least a mobile or email is required per row. Mobile numbers are normalized to +977.
          </p>
          <input #fileInput type="file" accept=".csv,text/csv" hidden (change)="onFile($event)" />
          <button mat-stroked-button (click)="fileInput.click()">
            <mat-icon>upload_file</mat-icon> Choose CSV file
          </button>
          @if (fileName()) { <span class="filename">{{ fileName() }}</span> }
        </div>
      }

      <!-- Step 2: preview -->
      @if (step() === 'preview' && preview(); as pv) {
        <div class="summary">
          <span class="chip chip--valid">{{ pv.valid }} valid</span>
          <span class="chip chip--duplicate">{{ pv.duplicate }} duplicate</span>
          <span class="chip chip--invalid">{{ pv.invalid }} invalid</span>
          <span class="muted">of {{ pv.total }} rows</span>
        </div>

        <div class="table-wrap">
          <table mat-table [dataSource]="pv.rows">
            <ng-container matColumnDef="row">
              <th mat-header-cell *matHeaderCellDef>#</th>
              <td mat-cell *matCellDef="let r">{{ r.row_number }}</td>
            </ng-container>
            <ng-container matColumnDef="name">
              <th mat-header-cell *matHeaderCellDef>Name</th>
              <td mat-cell *matCellDef="let r">{{ fullName(r) }}</td>
            </ng-container>
            <ng-container matColumnDef="mobile">
              <th mat-header-cell *matHeaderCellDef>Mobile</th>
              <td mat-cell *matCellDef="let r">{{ r.mobile_e164 ?? r.mobile ?? '—' }}</td>
            </ng-container>
            <ng-container matColumnDef="email">
              <th mat-header-cell *matHeaderCellDef>Email</th>
              <td mat-cell *matCellDef="let r">{{ r.email ?? '—' }}</td>
            </ng-container>
            <ng-container matColumnDef="status">
              <th mat-header-cell *matHeaderCellDef>Status</th>
              <td mat-cell *matCellDef="let r">
                <span class="chip chip--{{ r.row_status }}">{{ r.row_status }}</span>
                @if (r.errors.length) { <span class="err">{{ r.errors.join('; ') }}</span> }
              </td>
            </ng-container>
            <tr mat-header-row *matHeaderRowDef="cols"></tr>
            <tr mat-row *matRowDef="let row; columns: cols"></tr>
          </table>
        </div>

        <div class="dup-mode">
          <span>Duplicates:</span>
          <mat-radio-group [(ngModel)]="onDuplicate">
            <mat-radio-button value="skip">Skip</mat-radio-button>
            <mat-radio-button value="import_anyway">Import anyway</mat-radio-button>
          </mat-radio-group>
        </div>
        @if (importableCount() === 0) {
          <p class="muted">No rows will be imported with the current settings.</p>
        }
      }

      <!-- Step 3: done -->
      @if (step() === 'done' && result(); as res) {
        <div class="done">
          <mat-icon class="ok">check_circle</mat-icon>
          <p><strong>{{ res.imported }}</strong> contacts imported.</p>
          @if (res.skipped_duplicates) { <p class="muted">{{ res.skipped_duplicates }} duplicate(s) skipped.</p> }
          @if (res.failed) { <p class="muted">{{ res.failed }} row(s) failed.</p> }
        </div>
      }
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      @if (step() === 'upload') {
        <button mat-button (click)="ref.close(false)">Cancel</button>
      }
      @if (step() === 'preview') {
        <button mat-button (click)="reset()">Back</button>
        <button mat-flat-button color="primary" (click)="commit()" [disabled]="busy() || importableCount() === 0">
          Import {{ importableCount() }}
        </button>
      }
      @if (step() === 'done') {
        <button mat-flat-button color="primary" (click)="ref.close(true)">Done</button>
      }
    </mat-dialog-actions>
  `,
  styles: [
    `
      .hint { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); max-width: 560px; }
      .upload { display: flex; flex-direction: column; gap: 0.75rem; align-items: flex-start; padding: 0.5rem 0; min-width: 560px; }
      .filename { font: var(--mat-sys-body-small); }
      .summary { display: flex; gap: 0.5rem; align-items: center; margin-bottom: 0.75rem; }
      .table-wrap { max-height: 340px; overflow: auto; border: 1px solid var(--mat-sys-outline-variant); border-radius: 8px; }
      table { width: 100%; }
      .chip { text-transform: capitalize; padding: 0.1rem 0.55rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .chip--valid { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .chip--duplicate { background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); }
      .chip--invalid { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
      .err { display: block; color: var(--mat-sys-error); font: var(--mat-sys-label-small); margin-top: 0.15rem; }
      .dup-mode { display: flex; align-items: center; gap: 1rem; margin-top: 1rem; }
      .muted { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .done { display: flex; flex-direction: column; align-items: center; gap: 0.25rem; padding: 1.5rem; }
      .done .ok { color: var(--mat-sys-primary); font-size: 2.5rem; width: 2.5rem; height: 2.5rem; }
    `,
  ],
})
export class ContactImportDialogComponent {
  private readonly api = inject(ContactService);
  private readonly notify = inject(NotificationService);
  readonly ref = inject(MatDialogRef<ContactImportDialogComponent>);

  readonly cols = ['row', 'name', 'mobile', 'email', 'status'];
  readonly step = signal<'upload' | 'preview' | 'done'>('upload');
  readonly preview = signal<ImportPreview | null>(null);
  readonly result = signal<ImportResult | null>(null);
  readonly busy = signal(false);
  readonly fileName = signal<string | null>(null);
  onDuplicate: 'skip' | 'import_anyway' = 'skip';

  readonly importableCount = computed(() => {
    const pv = this.preview();
    if (!pv) return 0;
    return this.onDuplicate === 'import_anyway' ? pv.valid + pv.duplicate : pv.valid;
  });

  fullName(r: ImportRowResult): string {
    return [r.first_name, r.last_name].filter(Boolean).join(' ') || '—';
  }

  onFile(event: Event): void {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    this.fileName.set(file.name);
    this.busy.set(true);
    this.api.importPreview(file).subscribe({
      next: (pv) => { this.preview.set(pv); this.step.set('preview'); this.busy.set(false); },
      error: () => { this.busy.set(false); input.value = ''; },
    });
  }

  commit(): void {
    const pv = this.preview();
    if (!pv || this.busy()) return;
    // Send the rows that will actually be imported, as raw values (server re-normalizes).
    const wanted = this.onDuplicate === 'import_anyway'
      ? pv.rows.filter((r) => r.row_status === 'valid' || r.row_status === 'duplicate')
      : pv.rows.filter((r) => r.row_status === 'valid');
    const rows: ImportCommitRow[] = wanted.map((r) => ({
      first_name: r.first_name, last_name: r.last_name,
      mobile: r.mobile, landline: r.landline, email: r.email,
      tags: r.tags, notes: r.notes, status: r.status,
    }));
    this.busy.set(true);
    this.api.importCommit(rows, this.onDuplicate).subscribe({
      next: (res) => {
        this.result.set(res); this.step.set('done'); this.busy.set(false);
        this.notify.success(`Imported ${res.imported} contacts.`);
      },
      error: () => this.busy.set(false),
    });
  }

  reset(): void {
    this.step.set('upload');
    this.preview.set(null);
    this.fileName.set(null);
  }
}
