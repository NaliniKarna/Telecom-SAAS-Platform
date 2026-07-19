import {
  ChangeDetectionStrategy,
  Component,
  HostListener,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { SOLUTIONS } from '../solutions/solutions.data';

/**
 * Shared header for the public sub-pages (solutions, documentation). Mirrors the
 * landing page's light palette and chrome, with a click-toggle Solutions
 * dropdown and a Documentation link. Kept separate from the landing's own inline
 * nav to avoid disturbing that page's scroll-spy behavior.
 */
@Component({
  selector: 'app-public-header',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatIconModule],
  template: `
    <header class="ph" [class.ph--scrolled]="scrolled()">
      <div class="ph__inner">
        <a class="brand" routerLink="/" aria-label="Telecom Console home">
          <span class="brand__mark" aria-hidden="true">◈</span>
          <span class="brand__name">Telecom&nbsp;Console</span>
        </a>

        <nav class="ph__links" aria-label="Primary">
          <div class="menu">
            <button
              type="button"
              class="menu__btn"
              [class.is-open]="open() === 'sol'"
              (click)="toggle('sol', $event)"
              aria-haspopup="true"
              [attr.aria-expanded]="open() === 'sol'"
            >
              Solutions <mat-icon aria-hidden="true">expand_more</mat-icon>
            </button>
            @if (open() === 'sol') {
              <div class="dropdown" (click)="$event.stopPropagation()">
                @for (s of solutions; track s.slug) {
                  <a class="dropdown__item" [routerLink]="['/solutions', s.slug]" (click)="close()">
                    <span>{{ s.title }}</span>
                    @if (s.comingSoon) { <span class="soon">Soon</span> }
                    <span class="dropdown__tag">{{ s.tagline }}</span>
                  </a>
                }
              </div>
            }
          </div>
          <a routerLink="/docs">Documentation</a>
        </nav>

        <div class="ph__actions">
          <a class="btn btn--ghost" routerLink="/auth/login">Log in</a>
          <a class="btn btn--primary" routerLink="/auth/register">Register company</a>
        </div>
      </div>
    </header>
  `,
  styles: [
    `
      :host {
        --ink: var(--mat-sys-on-surface);
        --muted: var(--mat-sys-on-surface-variant);
        --primary: var(--mat-sys-primary);
        --bg: var(--mat-sys-surface-container-lowest);
        --soft: var(--mat-sys-surface);
        --tint: var(--mat-sys-surface-container-low);
        --border: var(--mat-sys-outline-variant);
        --font: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
        color-scheme: light;
        display: block;
        font-family: var(--font);
      }
      .ph {
        position: sticky;
        top: 0;
        z-index: 40;
        background: color-mix(in srgb, var(--bg) 85%, transparent);
        backdrop-filter: saturate(180%) blur(12px);
        border-bottom: 1px solid transparent;
        transition: border-color 0.25s ease;
      }
      .ph--scrolled {
        border-bottom-color: var(--border);
      }
      .ph__inner {
        max-width: 1140px;
        margin: 0 auto;
        padding: 0.9rem clamp(1.1rem, 4vw, 2rem);
        display: flex;
        align-items: center;
        gap: 1.5rem;
      }
      .brand {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        font-weight: 700;
        letter-spacing: -0.01em;
        color: var(--ink);
        text-decoration: none;
      }
      .brand__mark {
        color: var(--primary);
      }
      .ph__links {
        display: flex;
        align-items: center;
        gap: 1.4rem;
        margin-right: auto;
        margin-left: 1rem;
      }
      .ph__links > a,
      .menu__btn {
        font: inherit;
        font-size: 0.925rem;
        color: var(--muted);
        background: none;
        border: 0;
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 0.15rem;
        padding: 0;
        transition: color 0.15s ease;
      }
      .ph__links > a:hover,
      .menu__btn:hover,
      .menu__btn.is-open {
        color: var(--primary);
      }
      .menu__btn mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        transition: transform 0.2s ease;
      }
      .menu__btn.is-open mat-icon {
        transform: rotate(180deg);
      }
      .menu {
        position: relative;
      }
      .dropdown {
        position: absolute;
        top: calc(100% + 0.9rem);
        left: -0.75rem;
        width: 320px;
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: 14px;
        box-shadow: 0 1px 2px rgba(16, 24, 32, 0.06),
          0 20px 44px -24px rgba(16, 24, 32, 0.35);
        padding: 0.5rem;
        display: grid;
        gap: 0.15rem;
        animation: pop 0.16s ease;
      }
      @keyframes pop {
        from { opacity: 0; transform: translateY(-4px); }
        to { opacity: 1; transform: none; }
      }
      .dropdown__item {
        display: grid;
        grid-template-columns: auto auto;
        justify-content: start;
        align-items: center;
        gap: 0.4rem;
        padding: 0.55rem 0.65rem;
        border-radius: 10px;
        text-decoration: none;
        color: var(--ink);
        font-size: 0.9rem;
        font-weight: 600;
        transition: background 0.15s ease;
      }
      .dropdown__item:hover {
        background: var(--tint);
      }
      .dropdown__tag {
        grid-column: 1 / -1;
        font-weight: 400;
        font-size: 0.78rem;
        color: var(--muted);
      }
      .soon {
        font-size: 0.62rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--primary);
        background: color-mix(in srgb, var(--primary) 12%, transparent);
        border-radius: 999px;
        padding: 0.05rem 0.4rem;
      }
      .ph__actions {
        display: flex;
        align-items: center;
        gap: 0.6rem;
      }
      .btn {
        display: inline-flex;
        align-items: center;
        font-size: 0.9rem;
        font-weight: 550;
        padding: 0.55rem 0.95rem;
        border-radius: 10px;
        border: 1px solid transparent;
        text-decoration: none;
        cursor: pointer;
        transition: all 0.18s ease;
      }
      .btn--ghost {
        background: var(--bg);
        color: var(--ink);
        border-color: var(--border);
      }
      .btn--ghost:hover {
        background: var(--tint);
      }
      .btn--primary {
        color: #ffffff;
        background: linear-gradient(135deg,
          color-mix(in srgb, var(--primary) 82%, #17b3b3), var(--primary));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22),
          0 6px 16px -8px color-mix(in srgb, var(--primary) 60%, transparent);
      }
      .btn--primary:hover {
        transform: translateY(-1px);
      }
      a:focus-visible,
      button:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 3px;
        border-radius: 8px;
      }
      @media (max-width: 820px) {
        .ph__links {
          display: none;
        }
        .brand__name {
          display: none;
        }
      }
    `,
  ],
})
export class PublicHeaderComponent {
  readonly solutions = SOLUTIONS;
  readonly scrolled = signal(false);
  readonly open = signal<string | null>(null);

  @HostListener('window:scroll')
  onScroll(): void {
    this.scrolled.set(window.scrollY > 8);
  }

  @HostListener('document:click')
  onDocClick(): void {
    this.open.set(null);
  }

  @HostListener('document:keydown.escape')
  onEsc(): void {
    this.open.set(null);
  }

  toggle(name: string, ev: Event): void {
    ev.stopPropagation();
    this.open.set(this.open() === name ? null : name);
  }

  close(): void {
    this.open.set(null);
  }
}
