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

import { ContactListService } from './contact-list.service';
import { ContactGroup, ContactGroupMember } from './contact.models';
import { AddContactsDialogComponent } from './add-contacts-dialog.component';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-contact-group-detail',
  standalone: true,
  imports: [
    DatePipe, RouterLink, MatCardModule, MatButtonModule, MatIconModule,
    MatTabsModule, MatTableModule, MatProgressBarModule,
  ],
  template: `
    <a routerLink="/contact-lists" class="back"><mat-icon>arrow_back</mat-icon> Contact Lists</a>
    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (group(); as g) {
      <header class="page-header">
        <div>
          <h1>{{ g.name }}</h1>
          <span class="muted">{{ g.member_count }} member{{ g.member_count === 1 ? '' : 's' }}</span>
        </div>
        <button mat-stroked-button color="warn" (click)="remove(g)"><mat-icon>delete</mat-icon> Delete list</button>
      </header>
      <mat-tab-group>
        <mat-tab label="Overview">
          <mat-card appearance="outlined" class="tab-card">
            <mat-card-content>
              <dl class="meta">
                <dt>Name</dt><dd>{{ g.name }}</dd>
                <dt>Description</dt><dd>{{ g.description ?? '—' }}</dd>
                <dt>Members</dt><dd>{{ g.member_count }}</dd>
                <dt>Created</dt><dd>{{ g.created_at | date: 'medium' }}</dd>
              </dl>
            </mat-card-content>
          </mat-card>
        </mat-tab>
        <mat-tab label="Members">
          <div class="tab-actions">
            <button mat-flat-button color="primary" (click)="addContacts(g)"><mat-icon>person_add</mat-icon> Add contacts</button>
          </div>
          @if (members().length === 0) {
            <div class="empty"><mat-icon>group_off</mat-icon><p>No contacts in this list yet.</p></div>
          } @else {
            <mat-card appearance="outlined" class="tab-card">
              <table mat-table [dataSource]="members()">
                <ng-container matColumnDef="name">
                  <th mat-header-cell *matHeaderCellDef>Name</th>
                  <td mat-cell *matCellDef="let m">{{ name(m) }}</td>
                </ng-container>
                <ng-container matColumnDef="contact">
                  <th mat-header-cell *matHeaderCellDef>Mobile / Email</th>
                  <td mat-cell *matCellDef="let m">{{ m.mobile_e164 ?? m.email ?? '—' }}</td>
                </ng-container>
                <ng-container matColumnDef="added">
                  <th mat-header-cell *matHeaderCellDef>Added</th>
                  <td mat-cell *matCellDef="let m">{{ m.added_at | date: 'mediumDate' }}</td>
                </ng-container>
                <ng-container matColumnDef="actions">
                  <th mat-header-cell *matHeaderCellDef></th>
                  <td mat-cell *matCellDef="let m"><button mat-icon-button (click)="removeMember(g, m)" aria-label="Remove"><mat-icon>close</mat-icon></button></td>
                </ng-container>
                <tr mat-header-row *matHeaderRowDef="memberCols"></tr>
                <tr mat-row *matRowDef="let row; columns: memberCols"></tr>
              </table>
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
      .page-header h1 { font: var(--mat-sys-headline-medium); margin: 0 0 0.25rem; }
      .muted { color: var(--mat-sys-on-surface-variant); font: var(--mat-sys-body-small); }
      .tab-card { margin-top: 1rem; }
      .tab-actions { margin-top: 1rem; }
      table { width: 100%; }
      .meta { display: grid; grid-template-columns: auto 1fr; gap: 0.5rem 1.5rem; margin: 0; }
      .meta dt { color: var(--mat-sys-on-surface-variant); }
      .meta dd { margin: 0; }
      .empty { display: flex; flex-direction: column; align-items: center; gap: 0.5rem; padding: 2.5rem; color: var(--mat-sys-on-surface-variant); }
      .empty mat-icon { font-size: 2.5rem; width: 2.5rem; height: 2.5rem; opacity: 0.5; }
    `,
  ],
})
export class ContactGroupDetailComponent {
  private readonly api = inject(ContactListService);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  private readonly dialog = inject(MatDialog);
  private readonly notify = inject(NotificationService);

  readonly group = signal<ContactGroup | null>(null);
  readonly members = signal<ContactGroupMember[]>([]);
  readonly loading = signal(false);
  readonly memberCols = ['name', 'contact', 'added', 'actions'];
  private id = '';

  constructor() {
    this.id = this.route.snapshot.paramMap.get('id') ?? '';
    this.load();
  }
  load(): void {
    this.loading.set(true);
    this.api.get(this.id).subscribe({
      next: (g) => { this.group.set(g); this.loading.set(false); },
      error: () => { this.loading.set(false); this.router.navigate(['/contact-lists']); },
    });
    this.api.members(this.id).subscribe({ next: (m) => this.members.set(m) });
  }
  private refresh(members: ContactGroupMember[]): void {
    this.members.set(members);
    const g = this.group();
    if (g) this.group.set({ ...g, member_count: members.length });
  }
  name(m: ContactGroupMember): string { return [m.first_name, m.last_name].filter(Boolean).join(' ') || m.email || m.mobile_e164 || 'Contact'; }
  addContacts(g: ContactGroup): void {
    const existing = this.members().map((m) => m.contact_id);
    this.dialog.open(AddContactsDialogComponent, { data: { existing }, autoFocus: false })
      .afterClosed().subscribe((ids: string[] | false) => {
        if (!ids || ids.length === 0) return;
        this.api.addContacts(g.id, ids).subscribe({ next: (m) => { this.refresh(m); this.notify.success('Contacts added.'); } });
      });
  }
  removeMember(g: ContactGroup, m: ContactGroupMember): void {
    this.api.removeContact(g.id, m.contact_id).subscribe({ next: (list) => { this.refresh(list); this.notify.success('Contact removed.'); } });
  }
  remove(g: ContactGroup): void {
    this.api.remove(g.id).subscribe({ next: () => { this.notify.success('List deleted.'); this.router.navigate(['/contact-lists']); } });
  }
}
