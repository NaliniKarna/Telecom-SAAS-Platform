import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

import { SOLUTIONS } from '../solutions/solutions.data';

/** Shared footer for the public sub-pages (solutions, documentation). */
@Component({
  selector: 'app-public-footer',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink],
  template: `
    <footer class="foot">
      <div class="foot__inner">
        <div class="foot__brand">
          <span class="brand__mark" aria-hidden="true">◈</span>
          <span>Telecom Console</span>
          <p>Operations for SMS, voice and missed-call.</p>
        </div>
        <div class="foot__cols">
          <div>
            <h4>Solutions</h4>
            @for (s of solutions; track s.slug) {
              <a [routerLink]="['/solutions', s.slug]">{{ s.title }}</a>
            }
          </div>
          <div>
            <h4>Developers</h4>
            <a routerLink="/docs">Documentation</a>
          </div>
          <div>
            <h4>Access</h4>
            <a routerLink="/auth/login">Log in</a>
            <a routerLink="/auth/register">Register company</a>
          </div>
        </div>
      </div>
      <div class="foot__base">© 2026 Telecom Console</div>
    </footer>
  `,
  styles: [
    `
      :host {
        --ink: var(--mat-sys-on-surface);
        --muted: var(--mat-sys-on-surface-variant);
        --primary: var(--mat-sys-primary);
        --soft: var(--mat-sys-surface);
        --border: var(--mat-sys-outline-variant);
        color-scheme: light;
        display: block;
        font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
      }
      .foot {
        border-top: 1px solid var(--border);
        background: var(--soft);
        color: var(--ink);
      }
      .foot__inner {
        max-width: 1140px;
        margin: 0 auto;
        padding: clamp(2.5rem, 5vw, 3.5rem) clamp(1.1rem, 4vw, 2rem) 1.5rem;
        display: flex;
        justify-content: space-between;
        gap: 2rem;
        flex-wrap: wrap;
      }
      .foot__brand {
        max-width: 18rem;
      }
      .foot__brand span {
        font-weight: 700;
      }
      .brand__mark {
        color: var(--primary);
        margin-right: 0.4rem;
      }
      .foot__brand p {
        color: var(--muted);
        font-size: 0.875rem;
        margin: 0.6rem 0 0;
      }
      .foot__cols {
        display: flex;
        gap: clamp(2rem, 5vw, 4rem);
        flex-wrap: wrap;
      }
      .foot__cols h4 {
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: var(--muted);
        margin: 0 0 0.75rem;
      }
      .foot__cols a {
        display: block;
        font-size: 0.9rem;
        color: var(--muted);
        text-decoration: none;
        padding: 0.2rem 0;
        transition: color 0.15s ease;
      }
      .foot__cols a:hover {
        color: var(--primary);
      }
      .foot__base {
        max-width: 1140px;
        margin: 0 auto;
        padding: 1.25rem clamp(1.1rem, 4vw, 2rem);
        border-top: 1px solid var(--border);
        color: var(--muted);
        font-size: 0.85rem;
      }
    `,
  ],
})
export class PublicFooterComponent {
  readonly solutions = SOLUTIONS;
}
