import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MAT_DIALOG_DATA, MatDialogModule, MatDialogRef } from '@angular/material/dialog';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatCheckboxModule } from '@angular/material/checkbox';
import { MatListModule } from '@angular/material/list';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { UsersService } from '../users/users.service';
import { UserListItem } from '../users/user.models';

@Component({
  selector: 'app-add-members-dialog',
  standalone: true,
  imports: [
    FormsModule, MatDialogModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatCheckboxModule, MatListModule, MatProgressBarModule,
  ],
  template: `
    <h2 mat-dialog-title>Add members</h2>
    <mat-dialog-content>
      <mat-form-field appearance="outline" class="full">
        <mat-label>Search users</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="load()" placeholder="Name or email" />
      </mat-form-field>
      @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
      <div class="list">
        @for (u of candidates(); track u.id) {
          <label class="row">
            <mat-checkbox [checked]="selected().has(u.id)" (change)="toggle(u.id)" [disabled]="data.existing.includes(u.id)" />
            <span class="row__name">{{ name(u) }}</span>
            <span class="row__email">{{ u.email }}</span>
            @if (data.existing.includes(u.id)) { <span class="row__tag">already a member</span> }
          </label>
        } @empty {
          @if (!loading()) { <p class="muted">No users found.</p> }
        }
      </div>
    </mat-dialog-content>
    <mat-dialog-actions align="end">
      <button mat-button (click)="ref.close(false)">Cancel</button>
      <button mat-flat-button color="primary" (click)="confirm()" [disabled]="selected().size === 0">
        Add {{ selected().size || '' }}
      </button>
    </mat-dialog-actions>
  `,
  styles: [
    `
      .full { width: 100%; min-width: 420px; }
      .list { max-height: 320px; overflow: auto; }
      .row { display: flex; align-items: center; gap: 0.5rem; padding: 0.35rem 0; }
      .row__name { font-weight: 500; }
      .row__email { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .row__tag { margin-left: auto; color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-label-small); }
      .muted { color: var(--mat-sys-on-surface-variant); }
    `,
  ],
})
export class AddMembersDialogComponent {
  private readonly users = inject(UsersService);
  readonly ref = inject(MatDialogRef<AddMembersDialogComponent>);
  readonly data = inject<{ existing: string[] }>(MAT_DIALOG_DATA);

  readonly candidates = signal<UserListItem[]>([]);
  readonly selected = signal<Set<string>>(new Set());
  readonly loading = signal(false);
  search = '';

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.users.list({ search: this.search, size: 50 }).subscribe({
      next: (res) => { this.candidates.set(res.data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  name(u: UserListItem): string {
    return [u.first_name, u.last_name].filter(Boolean).join(' ') || u.email;
  }

  toggle(id: string): void {
    this.selected.update((s) => {
      const next = new Set(s);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  }

  confirm(): void {
    this.ref.close(Array.from(this.selected()));
  }
}
