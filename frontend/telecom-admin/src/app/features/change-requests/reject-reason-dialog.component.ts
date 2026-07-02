import { Component, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-reject-reason-dialog',
  standalone: true,
  imports: [FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule, MatButtonModule],
  template: `
    <h2 mat-dialog-title>Reject change request</h2>
    <mat-dialog-content>
      <p class="hint">Optionally tell the company admin why this was rejected.</p>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Reason (optional)</mat-label>
        <textarea matInput rows="3" [(ngModel)]="reason" maxlength="500"></textarea>
      </mat-form-field>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="warn" (click)="ref.close(reason)">Reject</button>
    </mat-dialog-actions>
  `,
  styles: [`.full { width: 100%; min-width: 360px; } .hint { color: var(--mat-sys-on-surface-variant); margin-top: 0; }`],
})
export class RejectReasonDialogComponent {
  readonly ref = inject(MatDialogRef<RejectReasonDialogComponent>);
  reason = '';
}
