import { Component, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, Router, RouterLink } from '@angular/router';
import { MatCardModule } from '@angular/material/card';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatTabsModule } from '@angular/material/tabs';
import { MatTableModule } from '@angular/material/table';
import { MatProgressBarModule } from '@angular/material/progress-bar';
import { MatDialog } from '@angular/material/dialog';

import { GroupService } from './group.service';
import { Group, GroupActivity, GroupMember } from './group.models';
import { AddMembersDialogComponent } from './add-members-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

const ACTION_LABELS: Record<string, string> = {
  create: 'Group created',
  update: 'Group updated',
  delete: 'Group deleted',
  member_added: 'Members added',
  member_removed: 'Member removed',
};

@Component({
  selector: 'app-group-detail',
  standalone: true,
  imports: [
    DatePipe, RouterLink, MatCardModule, MatButtonModule, MatIconModule,
    MatTabsModule, MatTableModule, MatProgressBarModule,
  ],
  template: `
    <a routerLink="/groups" class="back"><mat-icon>arrow_back</mat-icon> Groups</a>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }

    @if (group(); as g) {
      <header class="page-header">
        <div>
          <h1>{{ g.name }}</h1>
          <div class="badges">
            <span class="chip chip--type">{{ g.group_type }}</span>
            <span class="chip chip--{{ g.status }}">{{ g.status }}</span>
            <span class="muted">{{ g.member_count }} member{{ g.member_count === 1 ? '' : 's' }}</span>
          </div>
        </div>
        <button mat-stroked-button color="warn" (click)="remove(g)"><mat-icon>delete</mat-icon> Delete group</button>
      </header>

      <mat-tab-group>
        <!-- Overview -->
        <mat-tab label="Overview">
          <mat-card appearance="outlined" class="tab-card">
            <mat-card-content>
              <dl class="meta">
                <dt>Name</dt><dd>{{ g.name }}</dd>
                <dt>Description</dt><dd>{{ g.description ?? '—' }}</dd>
                <dt>Type</dt><dd>{{ g.group_type }}</dd>
                <dt>Status</dt><dd>{{ g.status }}</dd>
                <dt>Members</dt><dd>{{ g.member_count }}</dd>
                <dt>Created</dt><dd>{{ g.created_at | date: 'medium' }}</dd>
              </dl>
            </mat-card-content>
          </mat-card>
        </mat-tab>

        <!-- Members -->
        <mat-tab label="Members">
          <div class="tab-actions">
            <button mat-flat-button color="primary" (click)="addMembers(g)"><mat-icon>person_add</mat-icon> Add members</button>
          </div>
          @if (members().length === 0) {
            <div class="empty"><mat-icon>group_off</mat-icon><p>No members yet.</p></div>
          } @else {
            <mat-card appearance="outlined" class="tab-card">
              <table mat-table [dataSource]="members()">
                <ng-container matColumnDef="name">
                  <th mat-header-cell *matHeaderCellDef>Name</th>
                  <td mat-cell *matCellDef="let m">{{ m.full_name ?? '—' }}</td>
                </ng-container>
                <ng-container matColumnDef="email">
                  <th mat-header-cell *matHeaderCellDef>Email</th>
                  <td mat-cell *matCellDef="let m">{{ m.email }}</td>
                </ng-container>
                <ng-container matColumnDef="added">
                  <th mat-header-cell *matHeaderCellDef>Added</th>
                  <td mat-cell *matCellDef="let m">{{ m.added_at | date: 'mediumDate' }}</td>
                </ng-container>
                <ng-container matColumnDef="actions">
                  <th mat-header-cell *matHeaderCellDef></th>
                  <td mat-cell *matCellDef="let m">
                    <button mat-icon-button (click)="removeMember(g, m)" aria-label="Remove"><mat-icon>close</mat-icon></button>
                  </td>
                </ng-container>
                <tr mat-header-row *matHeaderRowDef="memberCols"></tr>
                <tr mat-row *matRowDef="let row; columns: memberCols"></tr>
              </table>
            </mat-card>
          }
        </mat-tab>

        <!-- Activity -->
        <mat-tab label="Activity">
          @if (activity().length === 0) {
            <div class="empty"><mat-icon>history</mat-icon><p>No activity yet.</p></div>
          } @else {
            <mat-card appearance="outlined" class="tab-card">
              <ul class="timeline">
                @for (a of activity(); track a.id) {
                  <li>
                    <mat-icon>{{ icon(a.action) }}</mat-icon>
                    <div>
                      <div class="timeline__action">{{ actionLabel(a.action) }}</div>
                      <div class="muted">{{ a.created_at | date: 'medium' }}</div>
                    </div>
                  </li>
                }
              </ul>
            </mat-card>
          }
        </mat-tab>
      </mat-tab-group>
    }
  `,
  styles: [
    `
      .back { display: inline-flex; align-items: center; gap: 0.25rem; color: var(--mat-sys-primary); text-decoration: none; margin-bottom: 1rem; }
      .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; }
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.5rem; }
      .badges { display: flex; align-items: center; gap: 0.5rem; }
      .tab-card { margin-top: 1rem; }
      .tab-actions { margin-top: 1rem; }
      table { width: 100%; }
      .meta { display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1.5rem; margin: 0; }
      .meta dt { color: var(--mat-sys-on-surface-variant); }
      .meta dd { margin: 0; }
      .chip { text-transform: capitalize; padding: 0.15rem 0.6rem; border-radius: 999px; font: var(--mat-sys-label-small); }
      .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
      .chip--inactive { background: var(--mat-sys-surface-container-highest); color: var(--mat-sys-on-surface-variant); }
      .chip--type { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); }
      .muted { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2.5rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
      .timeline { list-style: none; margin: 0; padding: 0; }
      .timeline li { display: flex; gap: 0.75rem; padding: 0.6rem 0; border-bottom: 1px solid var(--mat-sys-outline-variant); }
      .timeline li:last-child { border-bottom: none; }
      .timeline__action { font-weight: 500; }
    `,
  ],
})
export class GroupDetailComponent {
  private readonly api = inject(GroupService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly group = signal<Group | null>(null);
  readonly members = signal<GroupMember[]>([]);
  readonly activity = signal<GroupActivity[]>([]);
  readonly loading = signal(false);
  readonly memberCols = ['name', 'email', 'added', 'actions'];

  private id = '';

  constructor() {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }

  load(): void {
    this.loading.set(true);
    this.api.get(this.id).subscribe({
      next: (g) => { this.group.set(g); this.loading.set(false); },
      error: () => { this.loading.set(false); this.router.navigate(['/groups']); },
    });
    this.api.members(this.id).subscribe({ next: (m) => this.members.set(m) });
    this.api.activity(this.id).subscribe({ next: (a) => this.activity.set(a) });
  }

  private refreshCounts(members: GroupMember[]): void {
    this.members.set(members);
    const g = this.group();
    if (g) this.group.set({ ...g, member_count: members.length });
    this.api.activity(this.id).subscribe({ next: (a) => this.activity.set(a) });
  }

  addMembers(g: Group): void {
    const existing = this.members().map((m) => m.user_id);
    this.dialog.open(AddMembersDialogComponent, { data: { existing }, autoFocus: false })
      .afterClosed().subscribe((ids: string[] | false) => {
        if (!ids || ids.length === 0) return;
        this.api.addMembers(g.id, ids).subscribe({
          next: (m) => { this.refreshCounts(m); this.notify.success('Members added.'); },
        });
      });
  }

  removeMember(g: Group, m: GroupMember): void {
    this.api.removeMember(g.id, m.user_id).subscribe({
      next: (list) => { this.refreshCounts(list); this.notify.success('Member removed.'); },
    });
  }

  remove(g: Group): void {
    this.api.remove(g.id).subscribe({
      next: () => { this.notify.success('Group deleted.'); this.router.navigate(['/groups']); },
    });
  }

  actionLabel(a: string): string { return ACTION_LABELS[a] ?? a; }
  icon(a: string): string {
    return { create: 'add_circle', update: 'edit', delete: 'delete',
             member_added: 'person_add', member_removed: 'person_remove' }[a] ?? 'circle';
  }
}
