import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import {
  NavigationEnd,
  Router,
  RouterLink,
  RouterLinkActive,
} from '@angular/router';
import { filter, map, startWith } from 'rxjs/operators';

import { AuthService } from '../../../core/services/auth.service';
import { NavItem, NAV_ITEMS } from '../../navigation';

const EXPANDED_STORAGE_KEY = 'tlk.nav.expanded';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [MatListModule, MatIconModule, RouterLink, RouterLinkActive],
  template: `
    <nav class="sidebar">
      <mat-nav-list>
        @for (item of visibleItems(); track item.label) {
          @if (item.children) {
            <!-- Collapsible group parent -->
            <a
              mat-list-item
              role="button"
              tabindex="0"
              class="group-parent"
              [class.group-active]="isGroupActive(item)"
              [attr.aria-expanded]="isExpanded(item)"
              (click)="toggle(item)"
              (keydown.enter)="toggle(item)"
              (keydown.space)="toggle(item); $event.preventDefault()"
            >
              <mat-icon matListItemIcon>{{ item.icon }}</mat-icon>
              <span matListItemTitle>{{ item.label }}</span>
              <span
                matListItemMeta
                class="chevron"
                [class.chevron--open]="isExpanded(item)"
              >
                <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden="true">
                  <path
                    d="M6 9l6 6 6-6"
                    stroke="currentColor"
                    stroke-width="2"
                    stroke-linecap="round"
                    stroke-linejoin="round"
                  />
                </svg>
              </span>
            </a>

            @if (isExpanded(item)) {
              @for (child of item.children; track child.route) {
                <a
                  mat-list-item
                  class="group-child"
                  [routerLink]="child.route"
                  routerLinkActive="active-link"
                >
                  <mat-icon matListItemIcon>{{ child.icon }}</mat-icon>
                  <span matListItemTitle>{{ child.label }}</span>
                </a>
              }
            }
          } @else {
            <!-- Flat link item -->
            <a
              mat-list-item
              [routerLink]="item.route"
              routerLinkActive="active-link"
            >
              <mat-icon matListItemIcon>{{ item.icon }}</mat-icon>
              <span matListItemTitle>{{ item.label }}</span>
            </a>
          }
        }
      </mat-nav-list>
    </nav>
  `,
  styles: [
    `
      .sidebar {
        height: 100%;
        padding-top: 0.5rem;
      }
      .active-link {
        --mat-list-active-indicator-color: color-mix(
          in srgb,
          var(--mat-sys-primary) 14%,
          transparent
        );
        background: var(--mat-list-active-indicator-color);
        border-radius: 10px;
      }
      .active-link mat-icon,
      .active-link [matListItemTitle] {
        color: var(--mat-sys-primary);
      }
      mat-nav-list {
        padding: 0 0.5rem;
      }
      /* Group parent: same row styling as links; clickable without a route. */
      .group-parent {
        cursor: pointer;
      }
      .group-parent .chevron {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        color: var(--mat-sys-on-surface-variant);
        transition: transform 120ms ease;
        flex-shrink: 0;
      }
      .group-parent .chevron svg {
        display: block;
      }
      .group-parent .chevron.chevron--open {
        transform: rotate(180deg);
      }
      /* Highlight the parent (text/icon) when any child route is active,
         distinct from the solid active-link fill used by the live route. */
      .group-active [matListItemTitle],
      .group-active mat-icon {
        color: var(--mat-sys-primary);
        font-weight: 600;
      }
      /* Indent children so the group hierarchy reads clearly. */
      .group-child {
        padding-left: 1rem;
      }
    `,
  ],
})
export class SidebarComponent {
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);

  /** Reactive current URL (drives parent-active highlighting). */
  private readonly currentUrl = toSignal(
    this.router.events.pipe(
      filter((e): e is NavigationEnd => e instanceof NavigationEnd),
      map((e) => e.urlAfterRedirects),
      startWith(this.router.url),
    ),
    { initialValue: this.router.url },
  );

  /** Explicit expand/collapse choices, persisted across reloads. */
  private readonly expandedState = signal<Record<string, boolean>>(
    this.loadExpanded(),
  );

  /** Nav items the current user is allowed to see (groups + their children). */
  readonly visibleItems = computed<NavItem[]>(() => {
    // Touch signals for reactivity.
    this.auth.permissions();
    this.auth.isSuperAdmin();

    const result: NavItem[] = [];
    for (const item of NAV_ITEMS) {
      if (!this.canSee(item)) continue;

      if (item.children) {
        const children = item.children.filter((c) => this.canSee(c));
        if (children.length === 0) continue; // hide empty group entirely
        result.push({ ...item, children });
      } else {
        result.push(item);
      }
    }
    return result;
  });

  /** True when the live route belongs to this group (any child route). */
  isGroupActive(group: NavItem): boolean {
    const url = this.currentUrl();
    return (group.children ?? []).some(
      (c) => !!c.route && (url === c.route || url.startsWith(c.route + '/')),
    );
  }

  /**
   * Effective expanded state: an explicit user choice if one exists, otherwise
   * default to open whenever the group contains the active route.
   */
  isExpanded(group: NavItem): boolean {
    const explicit = this.expandedState()[group.label];
    return explicit ?? this.isGroupActive(group);
  }

  toggle(group: NavItem): void {
    const next = !this.isExpanded(group);
    const state = { ...this.expandedState(), [group.label]: next };
    this.expandedState.set(state);
    this.persistExpanded(state);
  }

  private canSee(item: NavItem): boolean {
    if (item.superAdminOnly && !this.auth.isSuperAdmin()) return false;
    if (item.hideForSuperAdmin && this.auth.isSuperAdmin()) return false;
    return !item.permissions || this.auth.hasAnyPermission(item.permissions);
  }

  private loadExpanded(): Record<string, boolean> {
    try {
      const raw = localStorage.getItem(EXPANDED_STORAGE_KEY);
      return raw ? (JSON.parse(raw) as Record<string, boolean>) : {};
    } catch {
      return {};
    }
  }

  private persistExpanded(state: Record<string, boolean>): void {
    try {
      localStorage.setItem(EXPANDED_STORAGE_KEY, JSON.stringify(state));
    } catch {
      /* storage unavailable (private mode / quota) — non-fatal */
    }
  }
}