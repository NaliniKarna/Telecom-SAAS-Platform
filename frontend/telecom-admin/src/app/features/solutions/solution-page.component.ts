import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { PublicHeaderComponent } from '../public/public-header.component';
import { PublicFooterComponent } from '../public/public-footer.component';
import { SOLUTIONS, solutionBySlug } from './solutions.data';

/**
 * Renders a single solution page from SOLUTIONS content, keyed by the :slug
 * route param. Standard structure: overview, key benefits, typical use cases,
 * how the platform helps, and a Register / Login call to action.
 */
@Component({
  selector: 'app-solution-page',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatIconModule, PublicHeaderComponent, PublicFooterComponent],
  template: `
    <app-public-header />

    @if (solution(); as s) {
      <main class="sp">
        <section class="hero">
          <a class="crumb" routerLink="/">← Back to home</a>
          <span class="eyebrow">
            Solutions
            @if (s.comingSoon) { <span class="soon">Coming soon</span> }
          </span>
          <h1>{{ s.title }}</h1>
          <p class="tagline">{{ s.tagline }}</p>
          <p class="overview">{{ s.overview }}</p>
          <div class="cta">
            <a class="btn btn--primary" routerLink="/auth/register">Register company</a>
            <a class="btn btn--ghost" routerLink="/auth/login">Log in</a>
          </div>
        </section>

        <section class="block">
          <h2>Key benefits</h2>
          <div class="benefits">
            @for (b of s.benefits; track b.title) {
              <article class="benefit">
                <mat-icon>check_circle</mat-icon>
                <h3>{{ b.title }}</h3>
                <p>{{ b.body }}</p>
              </article>
            }
          </div>
        </section>

        <section class="block split">
          <div>
            <h2>Typical use cases</h2>
            <ul class="ticks">
              @for (u of s.useCases; track u) {
                <li><mat-icon>arrow_right_alt</mat-icon> {{ u }}</li>
              }
            </ul>
          </div>
          <div>
            <h2>How the platform helps</h2>
            <ol class="steps">
              @for (h of s.howItHelps; track h) {
                <li>{{ h }}</li>
              }
            </ol>
          </div>
        </section>

        <section class="final">
          <div class="final__card">
            @if (s.comingSoon) {
              <h2>Be ready for {{ s.title }}</h2>
              <p>Register your company now so you're set up when this launches.</p>
            } @else {
              <h2>Ready to get started with {{ s.title }}?</h2>
              <p>Register your company and get set up after a quick review.</p>
            }
            <div class="cta">
              <a class="btn btn--primary" routerLink="/auth/register">Register company</a>
              <a class="btn btn--ghost" routerLink="/auth/login">Log in</a>
            </div>
          </div>
        </section>

        <section class="more">
          <h2>Explore other solutions</h2>
          <div class="more__grid">
            @for (o of others(); track o.slug) {
              <a class="more__card" [routerLink]="['/solutions', o.slug]">
                <span class="more__title">
                  {{ o.title }}
                  @if (o.comingSoon) { <span class="soon">Soon</span> }
                </span>
                <span class="more__tag">{{ o.tagline }}</span>
              </a>
            }
          </div>
        </section>
      </main>
    } @else {
      <main class="sp">
        <section class="hero">
          <a class="crumb" routerLink="/">← Back to home</a>
          <h1>Solution not found</h1>
          <p class="overview">The solution you're looking for doesn't exist.</p>
          <div class="cta">
            <a class="btn btn--primary" routerLink="/">Go home</a>
          </div>
        </section>
      </main>
    }

    <app-public-footer />
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
        background: var(--bg);
        color: var(--ink);
        font-family: var(--font);
      }
      .sp {
        max-width: 1040px;
        margin: 0 auto;
        padding: 0 clamp(1.1rem, 4vw, 2rem);
      }
      .crumb {
        display: inline-block;
        color: var(--muted);
        text-decoration: none;
        font-size: 0.875rem;
        margin: 1.5rem 0 1rem;
      }
      .crumb:hover { color: var(--primary); }
      .hero {
        padding: 1rem 0 2.5rem;
        border-bottom: 1px solid var(--border);
        background: radial-gradient(50rem 22rem at 88% -20%,
          color-mix(in srgb, var(--primary) 10%, transparent), transparent 60%);
      }
      .eyebrow {
        display: inline-flex;
        align-items: center;
        gap: 0.5rem;
        font-size: 0.72rem;
        font-weight: 650;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: var(--primary);
      }
      .soon {
        font-size: 0.62rem;
        font-weight: 700;
        color: var(--primary);
        background: color-mix(in srgb, var(--primary) 12%, transparent);
        border-radius: 999px;
        padding: 0.1rem 0.45rem;
        letter-spacing: 0.03em;
      }
      h1 {
        font-size: clamp(2.1rem, 4.5vw, 3rem);
        letter-spacing: -0.03em;
        line-height: 1.08;
        margin: 0.8rem 0 0.5rem;
      }
      .tagline {
        font-size: 1.2rem;
        color: var(--ink);
        margin: 0 0 1rem;
        font-weight: 500;
      }
      .overview {
        color: var(--muted);
        font-size: 1.05rem;
        line-height: 1.65;
        max-width: 60ch;
        margin: 0 0 1.6rem;
      }
      h2 {
        font-size: clamp(1.4rem, 2.6vw, 1.8rem);
        letter-spacing: -0.02em;
        margin: 0 0 1.3rem;
      }
      h3 {
        font-size: 1rem;
        margin: 0.6rem 0 0.3rem;
      }
      .block { padding: 3rem 0; border-bottom: 1px solid var(--border); }
      .benefits {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 1rem;
      }
      .benefit {
        background: var(--soft);
        border: 1px solid var(--border);
        border-radius: 14px;
        padding: 1.3rem 1.4rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
      }
      .benefit:hover {
        transform: translateY(-3px);
        border-color: color-mix(in srgb, var(--primary) 30%, var(--border));
      }
      .benefit mat-icon { color: var(--primary); }
      .benefit p { color: var(--muted); margin: 0; font-size: 0.92rem; line-height: 1.55; }
      .split {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: clamp(2rem, 5vw, 3.5rem);
      }
      .ticks, .steps { margin: 0; padding: 0; display: flex; flex-direction: column; gap: 0.7rem; }
      .ticks { list-style: none; }
      .ticks li { display: flex; align-items: center; gap: 0.5rem; color: var(--ink); }
      .ticks mat-icon { color: var(--primary); }
      .steps { counter-reset: s; list-style: none; }
      .steps li {
        position: relative;
        padding-left: 2.2rem;
        color: var(--muted);
        line-height: 1.55;
      }
      .steps li::before {
        counter-increment: s;
        content: counter(s);
        position: absolute;
        left: 0;
        top: 0;
        width: 1.6rem;
        height: 1.6rem;
        display: grid;
        place-items: center;
        border-radius: 50%;
        font-size: 0.8rem;
        font-weight: 700;
        color: #fff;
        background: var(--primary);
      }
      .final { padding: 3rem 0; }
      .final__card {
        text-align: center;
        border: 1px solid var(--border);
        border-radius: 22px;
        padding: clamp(2.2rem, 5vw, 3.2rem) 1.5rem;
        background: radial-gradient(40rem 18rem at 50% -30%,
          color-mix(in srgb, var(--primary) 12%, transparent), transparent 60%),
          linear-gradient(180deg, var(--bg), var(--tint));
      }
      .final__card p { color: var(--muted); margin: 0.4rem 0 1.4rem; }
      .cta { display: flex; gap: 0.7rem; flex-wrap: wrap; }
      .final .cta { justify-content: center; }
      .btn {
        display: inline-flex;
        align-items: center;
        font-weight: 550;
        font-size: 0.95rem;
        padding: 0.7rem 1.2rem;
        border-radius: 11px;
        border: 1px solid transparent;
        text-decoration: none;
        transition: all 0.18s ease;
      }
      .btn--primary {
        color: #fff;
        background: linear-gradient(135deg,
          color-mix(in srgb, var(--primary) 82%, #17b3b3), var(--primary));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.22),
          0 6px 16px -8px color-mix(in srgb, var(--primary) 60%, transparent);
      }
      .btn--primary:hover { transform: translateY(-1px); }
      .btn--ghost { background: var(--bg); color: var(--ink); border-color: var(--border); }
      .btn--ghost:hover { background: var(--tint); }
      .more { padding: 1rem 0 4rem; }
      .more__grid {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
      }
      .more__card {
        display: flex;
        flex-direction: column;
        gap: 0.25rem;
        padding: 1.1rem 1.2rem;
        border: 1px solid var(--border);
        border-radius: 14px;
        text-decoration: none;
        color: var(--ink);
        background: var(--bg);
        transition: transform 0.2s ease, border-color 0.2s ease;
      }
      .more__card:hover {
        transform: translateY(-3px);
        border-color: color-mix(in srgb, var(--primary) 30%, var(--border));
      }
      .more__title { font-weight: 650; display: inline-flex; align-items: center; gap: 0.5rem; }
      .more__tag { font-size: 0.83rem; color: var(--muted); }
      a:focus-visible, button:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 3px;
        border-radius: 8px;
      }
      @media (max-width: 820px) {
        .split, .benefits, .more__grid { grid-template-columns: 1fr; }
      }
    `,
  ],
})
export class SolutionPageComponent {
  private readonly route = inject(ActivatedRoute);
  private readonly params = toSignal(this.route.paramMap);

  readonly solution = computed(() => {
    const slug = this.params()?.get('slug') ?? '';
    return solutionBySlug(slug);
  });

  readonly others = computed(() => {
    const current = this.solution()?.slug;
    return SOLUTIONS.filter((s) => s.slug !== current).slice(0, 3);
  });
}
