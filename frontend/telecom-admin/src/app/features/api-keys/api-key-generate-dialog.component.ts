import { Component, inject, signal } from '@angular/core';
import { ReactiveFormsModule, FormBuilder, Validators } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatButtonModule } from '@angular/material/button';
import { MatChipsModule, MatChipInputEvent } from '@angular/material/chips';
import { MatIconModule } from '@angular/material/icon';

import { ApiKeyService } from './api-key.service';

// IPv4/IPv6 address or CIDR range. Kept intentionally permissive on IPv6
// (full validation happens server-side); this just catches obvious typos.
const IP_OR_CIDR_PATTERN =
  /^((\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?|[0-9a-fA-F:]+(\/\d{1,3})?)$/;

@Component({
  selector: 'app-api-key-generate-dialog',
  standalone: true,
  imports: [
    ReactiveFormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatSelectModule, MatButtonModule, MatChipsModule, MatIconModule,
  ],
  template: `
    <h2 mat-dialog-title>Generate API key</h2>
    <mat-dialog-content>
      <form [formGroup]="form" class="form">
        <mat-form-field appearance="outline">
          <mat-label>Name</mat-label>
          <input matInput formControlName="name" placeholder="e.g. Production server" />
          @if (form.controls.name.hasError('required') && form.controls.name.touched) {
            <mat-error>Name is required.</mat-error>
          }
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Description (optional)</mat-label>
          <textarea matInput rows="2" formControlName="description"></textarea>
        </mat-form-field>
        <mat-form-field appearance="outline">
          <mat-label>Expiry</mat-label>
          <mat-select formControlName="expiryPreset">
            <mat-option value="never">Never expires</mat-option>
            <mat-option value="30">30 days</mat-option>
            <mat-option value="60">60 days</mat-option>
            <mat-option value="90">90 days</mat-option>
            <mat-option value="365">1 year</mat-option>
            <mat-option value="custom">Custom date…</mat-option>
          </mat-select>
        </mat-form-field>
        @if (form.controls.expiryPreset.value === 'custom') {
          <mat-form-field appearance="outline">
            <mat-label>Custom expiry date</mat-label>
            <input matInput type="date" formControlName="customDate" [min]="minDate" />
          </mat-form-field>
        }
        <mat-form-field appearance="outline">
          <mat-label>Whitelisted IPs (optional)</mat-label>
          <mat-chip-grid #chipGrid>
            @for (ip of ipWhitelist(); track ip) {
              <mat-chip-row (removed)="removeIp(ip)">
                {{ ip }}
                <button matChipRemove aria-label="Remove IP"><mat-icon>cancel</mat-icon></button>
              </mat-chip-row>
            }
          </mat-chip-grid>
          <input
            placeholder="e.g. 203.0.113.5 or 10.0.0.0/24"
            [matChipInputFor]="chipGrid"
            (matChipInputTokenEnd)="addIp($event)"
          />
          <mat-hint>Leave empty to allow requests from any IP. Press enter to add each entry.</mat-hint>
          @if (ipError()) { <mat-error>{{ ipError() }}</mat-error> }
        </mat-form-field>
      </form>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="primary" (click)="submit()" [disabled]="saving() || form.invalid">Generate</button>
    </mat-dialog-actions>
  `,
  styles: [`
    .form { display: flex; flex-direction: column; gap: 0.5rem; min-width: 380px; padding-top: 0.5rem; }
    mat-error { font-size: 0.75rem; margin-top: 0.25rem; }
  `],
})
export class ApiKeyGenerateDialogComponent {
  private readonly fb = inject(FormBuilder);
  private readonly api = inject(ApiKeyService);
  readonly ref = inject(MatDialogRef<ApiKeyGenerateDialogComponent>);
  readonly saving = signal(false);
  readonly minDate = new Date(Date.now() + 86400000).toISOString().slice(0, 10);

  readonly ipWhitelist = signal<string[]>([]);
  readonly ipError = signal<string | null>(null);

  readonly form = this.fb.nonNullable.group({
    name: ['', [Validators.required]],
    description: this.fb.control<string | null>(null),
    expiryPreset: this.fb.nonNullable.control<string>('never'),
    customDate: this.fb.control<string | null>(null),
  });

  private computeExpiry(): string | null {
    const preset = this.form.controls.expiryPreset.value;
    if (preset === 'never') return null;
    if (preset === 'custom') {
      const d = this.form.controls.customDate.value;
      return d ? new Date(d + 'T23:59:59').toISOString() : null;
    }
    const days = parseInt(preset, 10);
    return new Date(Date.now() + days * 86400000).toISOString();
  }

  addIp(e: MatChipInputEvent): void {
    const v = (e.value || '').trim();
    if (v) {
      if (!IP_OR_CIDR_PATTERN.test(v)) {
        this.ipError.set(`"${v}" is not a valid IP address or CIDR range.`);
      } else if (!this.ipWhitelist().includes(v)) {
        this.ipWhitelist.update((ips) => [...ips, v]);
        this.ipError.set(null);
      }
    }
    e.chipInput!.clear();
  }

  removeIp(ip: string): void {
    this.ipWhitelist.update((ips) => ips.filter((x) => x !== ip));
  }

  submit(): void {
    if (this.form.invalid || this.saving()) { this.form.markAllAsTouched(); return; }
    this.saving.set(true);
    const { name, description } = this.form.getRawValue();
    this.api.generate({
      name,
      description,
      expires_at: this.computeExpiry(),
      ip_whitelist: this.ipWhitelist().length ? this.ipWhitelist() : null,
    }).subscribe({
      next: (created) => this.ref.close(created),
      error: () => this.saving.set(false),
    });
  }
}
