import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatSelectModule } from '@angular/material/select';
import { MatChipsModule } from '@angular/material/chips';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog } from '@angular/material/dialog';

import { GroupService } from './group.service';
import { GroupListItem, GroupStatus, GroupType } from './group.models';
import { GroupCreateDialogComponent } from './group-create-dialog.component';

@Component({
  selector: 'app-group-list',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule,
    MatIconModule, MatFormFieldModule, MatInputModule, MatSelectModule,
    MatChipsModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Groups</h1>
        <p>Organize users into groups. Groups don't grant permissions.</p>
      </div>
      <button mat-flat-button color="primary" (click)="create()">
        <mat-icon>add</mat-icon> New group
      </button>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="load()" placeholder="Group name" />
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Status</mat-label>
        <mat-select [(ngModel)]="status" (selectionChange)="load()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="active">Active</mat-option>
          <mat-option value="inactive">Inactive</mat-option>
        </mat-select>
      </mat-form-field>
      <mat-form-field appearance="outline">
        <mat-label>Type</mat-label>
        <mat-select [(ngModel)]="type" (selectionChange)="load()">
          <mat-option [value]="null">All</mat-option>
          <mat-option value="internal">Internal</mat-option>
        </mat-select>
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (!loading() && rows().length === 0) {
      <div class="empty">
        <mat-icon>groups</mat-icon>
        <p>No groups yet. Create your first group to organize users.</p>
      </div>
    }

    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let g">
              <div class="name">{{ g.name }}</div>
              @if (g.description) { <div class="desc">{{ g.description }}</div> }
            </td>
          </ng-container>
          <ng-container matColumnDef="type">
            <th mat-header-cell *matHeaderCellDef>Type</th>
            <td mat-cell *matCellDef="let g"><span class="chip chip--type">{{ g.group_type }}</span></td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let g"><span class="chip chip--{{ g.status }}">{{ g.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="members">
            <th mat-header-cell *matHeaderCellDef>Members</th>
            <td mat-cell *matCellDef="let g">{{ g.member_count }}</td>
          </ng-container>
          <ng-container matColumnDef="created">
            <th mat-header-cell *matHeaderCellDef>Created</th>
            <td mat-cell *matCellDef="let g">{{ g.created_at | date: 'mediumDate' }}</td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols" class="clickable" (click)="open(row)"></tr>
        </table>
      </mat-card>
    }
  `,
  styles: [
    `
      .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1.5rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .page-header p { color: var(--mat-sys-on-surface-variant); margin: 0; }
      .filters { display: flex; gap: 0.75rem; flex-wrap: wrap; margin-bottom: 1rem; }
      .filters mat-form-field { min-width: 180px; }
      table { width: 100%; }
      .name { font-weight: 500; }
      .desc { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .clickable { cursor: pointer; }
      .chip { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .chip--inactive { background: var(--mat-sys-surface-container-highest); color: var(--mat-sys-on-surface-variant); }
      .chip--type { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
    `,
  ],
})
export class GroupListComponent {
  private readonly api = inject(GroupService);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);

  readonly cols = ['name', 'type', 'status', 'members', 'created'];
  readonly rows = signal<GroupListItem[]>([]);
  readonly loading = signal(false);
  search = '';
  status: GroupStatus | null = null;
  type: GroupType | null = null;

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.list({ search: this.search, status: this.status, group_type: this.type }).subscribe({
      next: (res) => { this.rows.set(res.data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }

  open(g: GroupListItem): void { this.router.navigate(['/groups', g.id]); }

  create(): void {
    this.dialog.open(GroupCreateDialogComponent, { autoFocus: false })
      .afterClosed().subscribe((g) => { if (g) this.router.navigate(['/groups', g.id]); });
  }
}
