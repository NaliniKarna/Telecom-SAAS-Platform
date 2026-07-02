import { Component, inject, signal } from '@angular/core';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';

import { ApiKeyCreated } from './api-key.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-api-key-reveal-dialog',
  standalone: true,
  imports: [MatDialogModule, MatButtonModule, MatIconModule],
  template: `
    <h2 mat-dialog-title>Copy your API key</h2>
    <mat-dialog-content>
      <div class="warn">
        <mat-icon>warning</mat-icon>
        <span>This is the only time the key will be shown. Copy it now and store it securely — you won't be able to see it again.</span>
      </div>
      <div class="keybox">
        <code>{{ data.api_key }}</code>
        <button mat-icon-button (click)="copy()" aria-label="Copy"><mat-icon>content_copy</mat-icon></button>
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-flat-button color="primary" (click)="ref.close(true)">Done</button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .warn { display: flex; gap: 0.5rem; align-items: flex-start; padding: 0.75rem; border-radius: 8px;
        background: var(--mat-sys-tertiary-container); color: var(--mat-sys-on-tertiary-container); margin-bottom: 1rem; max-width: 460px; }
      .keybox { display: flex; align-items: center; gap: 0.5rem; padding: 0.5rem 0.75rem; border-radius: 8px;
        background: var(--mat-sys-surface-container-highest); }
      .keybox code { font-family: monospace; word-break: break-all; flex: 1; }
    `,
  ],
})
export class ApiKeyRevealDialogComponent {
  readonly ref = inject(MatDialogRef<ApiKeyRevealDialogComponent>);
  readonly data = inject<ApiKeyCreated>(MAT_DIALOG_DATA);
  private readonly notify = inject(NotificationService);
  readonly copied = signal(false);

  copy(): void {
    navigator.clipboard?.writeText(this.data.api_key).then(
      () => { this.copied.set(true); this.notify.success('API key copied to clipboard.'); },
      () => this.notify.success('Select and copy the key manually.'),
    );
  }
}
