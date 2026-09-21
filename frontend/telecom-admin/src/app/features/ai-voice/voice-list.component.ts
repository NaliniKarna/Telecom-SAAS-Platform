import { Component, inject, signal } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatTableModule } from '@angular/material/table';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AiVoiceService } from './ai-voice.service';
import { Voice } from './ai-voice.models';
import { NotificationService } from '../../core/services/notification.service';

@Component({
  selector: 'app-voice-list',
  standalone: true,
  imports: [
    MatCardModule, MatTableModule, MatButtonModule, MatIconModule,
    MatMenuModule, MatProgressBarModule,
  ],
  template: `
    <header class="page-header">
      <div><h1>Voices</h1><p>Voices available for AI Voice Templates.</p></div>
    </header>

    @if (loading()) { <mat-progress-bar mode="indeterminate" /> }
    @if (!loading() && rows().length === 0) {
      <div class="empty"><mat-icon>graphic_eq</mat-icon><p>No voices available yet.</p></div>
    }
    @if (rows().length > 0) {
      <mat-card appearance="outlined">
        <table mat-table [dataSource]="rows()">
          <ng-container matColumnDef="name">
            <th mat-header-cell *matHeaderCellDef>Name</th>
            <td mat-cell *matCellDef="let v">
              <strong>{{ v.name }}</strong>
              @if (v.description) { <div class="sub">{{ v.description }}</div> }
            </td>
          </ng-container>
          <ng-container matColumnDef="language">
            <th mat-header-cell *matHeaderCellDef>Language</th>
            <td mat-cell *matCellDef="let v">{{ v.language }}</td>
          </ng-container>
          <ng-container matColumnDef="gender">
            <th mat-header-cell *matHeaderCellDef>Gender</th>
            <td mat-cell *matCellDef="let v">{{ v.gender || '—' }}</td>
          </ng-container>
          <ng-container matColumnDef="provider">
            <th mat-header-cell *matHeaderCellDef>Provider</th>
            <td mat-cell *matCellDef="let v"><span class="tag">{{ v.provider }}</span></td>
          </ng-container>
          <ng-container matColumnDef="status">
            <th mat-header-cell *matHeaderCellDef>Status</th>
            <td mat-cell *matCellDef="let v"><span class="chip chip--{{ v.status }}">{{ v.status }}</span></td>
          </ng-container>
          <ng-container matColumnDef="actions">
            <th mat-header-cell *matHeaderCellDef></th>
            <td mat-cell *matCellDef="let v">
              <button mat-icon-button [matMenuTriggerFor]="menu"><mat-icon>more_vert</mat-icon></button>
              <mat-menu #menu="matMenu">
                @if (v.status === 'active') {
                  <button mat-menu-item (click)="deactivate(v)"><mat-icon>toggle_off</mat-icon> Deactivate</button>
                } @else {
                  <button mat-menu-item (click)="activate(v)"><mat-icon>toggle_on</mat-icon> Activate</button>
                }
              </mat-menu>
            </td>
          </ng-container>
          <tr mat-header-row *matHeaderRowDef="cols"></tr>
          <tr mat-row *matRowDef="let row; columns: cols"></tr>
        </table>
      </mat-card>
    }
  `,
  styles: [`
    .page-header { display: flex; align-items: flex-start; justify-content: space-between; margin-bottom: 1rem; gap: 1rem; }
    .page-header h1 { margin: 0 0 .25rem; } .page-header p { margin: 0; color: var(--mat-sys-on-surface-variant); }
    table { width: 100%; }
    .sub { color: var(--mat-sys-on-surface-variant); font-size: .8rem; max-width: 420px; }
    .tag { background: var(--mat-sys-secondary-container); color: var(--mat-sys-on-secondary-container); padding: .1rem .5rem; border-radius: 999px; font-size: .72rem; }
    .chip { text-transform: capitalize; padding: .15rem .6rem; border-radius: 999px; font-size: .78rem; background: var(--mat-sys-surface-container-highest); }
    .chip--active { background: var(--mat-sys-primary-container); color: var(--mat-sys-on-primary-container); }
    .chip--inactive { background: var(--mat-sys-error-container); color: var(--mat-sys-on-error-container); }
    .empty { display: flex; flex-direction: column; align-items: center; gap: .5rem; padding: 3rem; color: var(--mat-sys-on-surface-variant); }
    .empty mat-icon { font-size: 2.5rem; height: 2.5rem; width: 2.5rem; opacity: .5; }
  `],
})
export class VoiceListComponent {
  private readonly api = inject(AiVoiceService);
  private readonly notify = inject(NotificationService);

  readonly cols = ['name', 'language', 'gender', 'provider', 'status', 'actions'];
  readonly rows = signal<Voice[]>([]);
  readonly loading = signal(false);

  constructor() { this.load(); }

  load(): void {
    this.loading.set(true);
    this.api.listVoices({ size: 100 }).subscribe({
      next: (res) => { this.rows.set(res.data); this.loading.set(false); },
      error: () => { this.loading.set(false); this.notify.error('Unable to load voices.'); },
    });
  }

  activate(v: Voice): void {
    this.api.activateVoice(v.id).subscribe({
      next: () => { this.notify.success('Voice activated.'); this.load(); },
      error: () => this.notify.error('Unable to activate voice.'),
    });
  }
  deactivate(v: Voice): void {
    this.api.deactivateVoice(v.id).subscribe({
      next: () => { this.notify.success('Voice deactivated.'); this.load(); },
      error: () => this.notify.error('Unable to deactivate voice.'),
    });
  }
}
