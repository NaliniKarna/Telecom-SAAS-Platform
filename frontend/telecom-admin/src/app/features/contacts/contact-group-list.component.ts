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
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog } from '@angular/material/dialog';

import { ContactListService } from './contact-list.service';
import { ContactGroup } from './contact.models';
import { ContactGroupCreateDialogComponent } from './contact-group-create-dialog.component';

@Component({
  selector: 'app-contact-group-list',
  standalone: true,
  imports: [
    DatePipe, FormsModule, MatCardModule, MatTableModule, MatButtonModule,
    MatIconModule, MatFormFieldModule, MatInputModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div>
        <h1>Contact Groups</h1>
        <p>Organize contacts into groups for campaigns and messaging.</p>
      </div>
      <button mat-flat-button color="primary" (click)="create()"><mat-icon>add</mat-icon> New group</button>
    </header>

    <div class="filters">
      <mat-form-field appearance="outline">
        <mat-label>Search</mat-label>
        <input matInput [(ngModel)]="search" (keyup.enter)="load()" placeholder="Group name" />
      </mat-form-field>
    </div>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>format_list_bulleted</mat-icon><p>No contact groups yet.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let g"><div class="name">{{ g.name }}</div>@if (g.description) { <div class="desc">{{ g.description }}</div> }</td>
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
      .filters { margin-bottom: 1rem; }
      table { width: 100%; }
      .name { font-weight: 500; }
      .desc { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .clickable { cursor: pointer; }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
    `,
  ],
})
export class ContactGroupListComponent {
  private readonly api = inject(ContactListService);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  readonly cols = ['name', 'members', 'created'];
  readonly rows = signal<ContactGroup[]>([]);
  readonly loading = signal(false);
  search = '';
  constructor() { this.load(); }
  load(): void {
    this.loading.set(true);
    this.api.list(this.search).subscribe({
      next: (res) => { this.rows.set(res.data); this.loading.set(false); },
      error: () => this.loading.set(false),
    });
  }
  open(g: ContactGroup): void { this.router.navigate(['/contact-lists', g.id]); }
  create(): void {
    this.dialog.open(ContactGroupCreateDialogComponent, { autoFocus: false })
      .afterClosed().subscribe((g) => { if (g) this.router.navigate(['/contact-lists', g.id]); });
  }
}
