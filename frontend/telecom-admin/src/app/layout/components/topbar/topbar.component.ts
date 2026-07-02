import { Component, EventEmitter, inject, Output } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatMenuModule } from '@angular/material/menu';
import { MatTooltipModule } from '@angular/material/tooltip';

import { AuthService } from '../../../core/services/auth.service';
import { ThemeService } from '../../../core/services/theme.service';

@Component({
  selector: 'app-topbar',
  standalone: true,
  imports: [RouterLink, MatToolbarModule, MatButtonModule, MatIconModule, MatMenuModule, MatTooltipModule],
  template: `
    <mat-toolbar class="topbar">
      <button
        mat-icon-button
        aria-label="Toggle navigation"
        (click)="toggleSidenav.emit()"
      >
        <mat-icon>menu</mat-icon>
      </button>

      <span class="topbar__title">Telecom Console</span>
      <span class="topbar__spacer"></span>

      <button
        mat-icon-button
        [attr.aria-label]="theme.label()"
        [matTooltip]="theme.label()"
        (click)="theme.cycle()"
      >
        <mat-icon>{{ theme.icon() }}</mat-icon>
      </button>

      <button mat-button [matMenuTriggerFor]="userMenu" class="topbar__user">
        <mat-icon>account_circle</mat-icon>
        <span class="topbar__email">{{ auth.user()?.email }}</span>
      </button>

      <mat-menu #userMenu="matMenu">
        <div class="user-menu__header">
          <div class="user-menu__name">{{ displayName() }}</div>
          <div class="user-menu__role">{{ primaryRole() }}</div>
        </div>
        <button mat-menu-item routerLink="/profile">
          <mat-icon>person</mat-icon>
          <span>My Profile</span>
        </button>
        <button mat-menu-item routerLink="/profile" [queryParams]="{ changePassword: 1 }">
          <mat-icon>lock</mat-icon>
          <span>Change Password</span>
        </button>
        <button mat-menu-item (click)="auth.logout()">
          <mat-icon>logout</mat-icon>
          <span>Sign out</span>
        </button>
      </mat-menu>
    </mat-toolbar>
  `,
  styles: [
    `
      .topbar {
        position: sticky;
        top: 0;
        z-index: 5;
        gap: 0.5rem;
        background: var(--mat-sys-surface-container);
        border-bottom: 1px solid var(--mat-sys-outline-variant);
      }
      .topbar__title {
        font: var(--mat-sys-title-medium);
      }
      .topbar__spacer {
        flex: 1 1 auto;
      }
      .topbar__user {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
      }
      .topbar__email {
        max-width: 16rem;
        overflow: hidden;
        text-overflow: ellipsis;
      }
      .user-menu__header {
        padding: 0.75rem 1rem;
        border-bottom: 1px solid var(--mat-sys-outline-variant);
      }
      .user-menu__name {
        font: var(--mat-sys-title-small);
      }
      .user-menu__role {
        font: var(--mat-sys-body-small);
        color: var(--mat-sys-on-surface-variant);
        text-transform: capitalize;
      }
    `,
  ],
})
export class TopbarComponent {
  @Output() toggleSidenav = new EventEmitter<void>();
  readonly auth = inject(AuthService);
  readonly theme = inject(ThemeService);

  displayName(): string {
    const u = this.auth.user();
    if (!u) return '';
    const name = [u.first_name, u.last_name].filter(Boolean).join(' ');
    return name || u.email;
  }

  primaryRole(): string {
    return this.auth.roles()[0]?.replace(/_/g, ' ') ?? '';
  }
}
