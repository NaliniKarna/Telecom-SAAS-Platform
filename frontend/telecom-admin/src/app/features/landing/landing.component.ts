import {
  AfterViewInit,
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  HostListener,
  inject,
  signal,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatIconModule } from '@angular/material/icon';

import { SOLUTIONS } from '../solutions/solutions.data';

/**
 * Public landing page — the unauthenticated entry point for Telecom Console.
 *
 * Light enterprise homepage that reuses the application's Material 3 palette
 * (cyan "signal" primary — the same tokens the login / register screens use).
 * `color-scheme: light` pins the Material `light-dark()` tokens to their light
 * values, so the surface never goes dark regardless of OS theme while the accent
 * stays consistent with the rest of the app.
 *
 * Motion: gentle, once-only fade-up reveals as sections enter the viewport, plus
 * smooth in-page anchor scrolling — all disabled under prefers-reduced-motion.
 *
 * Links resolve to real destinations only: in-page sections that exist here and
 * the two public routes (/auth/login, /auth/register). No links point at pages
 * that don't exist in the product.
 */
@Component({
  selector: 'app-landing',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  imports: [RouterLink, MatIconModule],
  template: `
    <div class="lp">
      <!-- Navigation -->
      <header class="nav" [class.nav--scrolled]="scrolled()">
        <div class="nav__inner">
          <a class="brand" href="#top" (click)="go('top', $event)" aria-label="Telecom Console home">
            <span class="brand__mark" aria-hidden="true">◈</span>
            <span class="brand__name">Telecom&nbsp;Console</span>
          </a>

          <nav class="nav__links" aria-label="Primary">
            <a href="#capabilities" (click)="go('capabilities', $event)">Platform</a>

            <div class="ddown">
              <button
                type="button"
                class="ddown__btn"
                [class.is-open]="menu() === 'sol'"
                (click)="toggleMenu('sol', $event)"
                aria-haspopup="true"
                [attr.aria-expanded]="menu() === 'sol'"
              >
                Solutions <mat-icon aria-hidden="true">expand_more</mat-icon>
              </button>
              @if (menu() === 'sol') {
                <div class="ddown__menu" (click)="$event.stopPropagation()">
                  @for (s of solutions; track s.slug) {
                    <a class="ddown__item" [routerLink]="['/solutions', s.slug]" (click)="closeMenu()">
                      <span class="ddown__t">{{ s.title }}
                        @if (s.comingSoon) { <span class="soon">Soon</span> }
                      </span>
                      <span class="ddown__d">{{ s.tagline }}</span>
                    </a>
                  }
                </div>
              }
            </div>

            <a href="#security" (click)="go('security', $event)">Security</a>

            <div class="ddown">
              <button
                type="button"
                class="ddown__btn"
                [class.is-open]="menu() === 'dev'"
                (click)="toggleMenu('dev', $event)"
                aria-haspopup="true"
                [attr.aria-expanded]="menu() === 'dev'"
              >
                Developers <mat-icon aria-hidden="true">expand_more</mat-icon>
              </button>
              @if (menu() === 'dev') {
                <div class="ddown__menu" (click)="$event.stopPropagation()">
                  <a class="ddown__item" routerLink="/docs" (click)="closeMenu()">
                    <span class="ddown__t">Documentation</span>
                    <span class="ddown__d">API reference and developer guides</span>
                  </a>
                  <a class="ddown__item" href="#developers" (click)="closeMenu(); go('developers', $event)">
                    <span class="ddown__t">API overview</span>
                    <span class="ddown__d">How the developer API works</span>
                  </a>
                </div>
              }
            </div>
          </nav>

          <div class="nav__actions">
            <a class="btn btn--ghost" routerLink="/auth/login">Log in</a>
            <a class="btn btn--primary" routerLink="/auth/register">
              Register company
            </a>
          </div>
        </div>
      </header>

      <main id="top">
        <!-- Hero -->
        <section class="hero">
          <div class="hero__copy reveal">
            <span class="eyebrow">Unified communications platform</span>
            <h1>Every channel, one console.</h1>
            <p class="lead">
              Run SMS, voice, and missed-call services across every team from a
              single operations console — with role-based access, live delivery
              analytics, and a clean developer API.
            </p>
            <div class="hero__cta">
              <a class="btn btn--primary btn--lg" routerLink="/auth/register">
                Register company
              </a>
              <a class="btn btn--ghost btn--lg" routerLink="/auth/login">
                Log in <mat-icon aria-hidden="true">arrow_forward</mat-icon>
              </a>
            </div>
            <p class="hero__note">
              Company registration is reviewed before access is granted.
            </p>
          </div>

          <!-- Integrated product preview -->
          <div class="preview reveal" style="transition-delay: 0.1s" aria-hidden="true">
            <div class="window">
              <div class="window__bar">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                <span class="window__label">Telecom Console</span>
              </div>
              <div class="app">
                <aside class="app__side">
                  <div class="app__brand"><span>◈</span> Console</div>
                  <span class="app__nav is-active"><mat-icon>dashboard</mat-icon> Overview</span>
                  <span class="app__nav"><mat-icon>campaign</mat-icon> Campaigns</span>
                  <span class="app__nav"><mat-icon>call</mat-icon> Voice</span>
                  <span class="app__nav"><mat-icon>dialpad</mat-icon> Numbers</span>
                  <span class="app__nav"><mat-icon>insights</mat-icon> Analytics</span>
                </aside>
                <div class="app__main">
                  <div class="app__head">
                    <div>
                      <div class="app__title">Overview</div>
                      <div class="app__sub">Last 7 days</div>
                    </div>
                    <span class="pill">Live</span>
                  </div>
                  <div class="stats">
                    <div class="stat">
                      <span class="stat__k">Messages sent</span>
                      <span class="stat__v">128,940</span>
                      <span class="stat__d up">+6.2%</span>
                    </div>
                    <div class="stat">
                      <span class="stat__k">Delivery rate</span>
                      <span class="stat__v">97.4%</span>
                      <span class="stat__d up">+0.8%</span>
                    </div>
                    <div class="stat">
                      <span class="stat__k">Active campaigns</span>
                      <span class="stat__v">12</span>
                      <span class="stat__d">steady</span>
                    </div>
                  </div>
                  <div class="chart">
                    <svg viewBox="0 0 320 96" preserveAspectRatio="none">
                      <defs>
                        <linearGradient id="area" x1="0" y1="0" x2="0" y2="1">
                          <stop offset="0" stop-color="var(--primary)" stop-opacity="0.20" />
                          <stop offset="1" stop-color="var(--primary)" stop-opacity="0" />
                        </linearGradient>
                      </defs>
                      <path class="spark-area" d="M0,78 L40,66 L80,70 L120,48 L160,54 L200,32 L240,38 L280,20 L320,26 L320,96 L0,96 Z" fill="url(#area)"/>
                      <path class="spark-line" d="M0,78 L40,66 L80,70 L120,48 L160,54 L200,32 L240,38 L280,20 L320,26" fill="none" stroke="var(--primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <!-- Platform capabilities -->
        <section id="capabilities" class="section">
          <div class="section__head reveal">
            <span class="eyebrow">Platform</span>
            <h2>Everything you send, in one place.</h2>
            <p class="section__lead">
              Four capabilities on one console — no stitching tools together, no
              context switching.
            </p>
          </div>
          <div class="cards">
            <article class="card reveal">
              <div class="card__icon"><mat-icon>sms</mat-icon></div>
              <h3>SMS broadcasting</h3>
              <p>Campaigns, templates, sender IDs, and delivery tracking.</p>
            </article>
            <article class="card reveal" style="transition-delay: 0.06s">
              <div class="card__icon"><mat-icon>call</mat-icon></div>
              <h3>Voice calls</h3>
              <p>Originate and manage calls through your platform PBX.</p>
            </article>
            <article class="card reveal" style="transition-delay: 0.12s">
              <div class="card__icon"><mat-icon>phone_missed</mat-icon></div>
              <h3>Missed-call services</h3>
              <p>Capture missed-call signals and trigger callbacks.</p>
            </article>
            <article class="card reveal" style="transition-delay: 0.18s">
              <div class="card__icon"><mat-icon>api</mat-icon></div>
              <h3>Developer API</h3>
              <p>Integrate messaging and voice with keys and webhooks.</p>
            </article>
          </div>
        </section>

        <!-- Product / analytics highlight -->
        <section id="preview" class="section split">
          <div class="split__copy reveal">
            <span class="eyebrow">Analytics</span>
            <h2>Delivery you can actually see.</h2>
            <p class="section__lead">
              Real-time delivery rates, per-campaign breakdowns, and message
              tracking, so teams act on what is happening now.
            </p>
            <ul class="ticks">
              <li><mat-icon>check</mat-icon> Live delivery and failure rates</li>
              <li><mat-icon>check</mat-icon> Per-campaign and per-tenant views</li>
              <li><mat-icon>check</mat-icon> Message-level status tracking</li>
            </ul>
          </div>
          <div class="split__visual reveal" style="transition-delay: 0.08s">
            <div class="panel">
              <div class="panel__head">
                <span>Delivery by channel</span><span class="pill soft">7d</span>
              </div>
              <div class="bars">
                <div class="bar"><i style="height:82%"></i><span>SMS</span></div>
                <div class="bar"><i style="height:64%"></i><span>Voice</span></div>
                <div class="bar"><i style="height:46%"></i><span>Missed</span></div>
                <div class="bar alt"><i style="height:92%"></i><span>API</span></div>
              </div>
            </div>
          </div>
        </section>

        <!-- Security & reliability -->
        <section id="security" class="section">
          <div class="section__head reveal">
            <span class="eyebrow">Security and reliability</span>
            <h2>Built for teams that cannot afford surprises.</h2>
          </div>
          <div class="grid-3">
            <article class="feature reveal">
              <mat-icon>admin_panel_settings</mat-icon>
              <h3>Role-based access</h3>
              <p>Granular RBAC across every tenant, with clear separation of duties.</p>
            </article>
            <article class="feature reveal" style="transition-delay: 0.06s">
              <mat-icon>lock</mat-icon>
              <h3>Encrypted and isolated</h3>
              <p>Credentials encrypted at rest and strict per-tenant data isolation.</p>
            </article>
            <article class="feature reveal" style="transition-delay: 0.12s">
              <mat-icon>fact_check</mat-icon>
              <h3>Full audit trail</h3>
              <p>Every sensitive action is recorded and reviewable by administrators.</p>
            </article>
          </div>
        </section>

        <!-- Developer / API -->
        <section id="developers" class="section split">
          <div class="split__copy reveal">
            <span class="eyebrow">Developers</span>
            <h2>An API that gets out of your way.</h2>
            <p class="section__lead">
              Provision keys, send messages, and subscribe to delivery webhooks
              with a predictable REST API and clear versioning.
            </p>
            <ul class="ticks">
              <li><mat-icon>check</mat-icon> Scoped API keys and rotation</li>
              <li><mat-icon>check</mat-icon> Delivery webhooks</li>
              <li><mat-icon>check</mat-icon> Versioned, documented endpoints</li>
            </ul>
          </div>
          <div class="split__visual reveal" style="transition-delay: 0.08s">
            <div class="code">
              <div class="code__bar">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
                <span class="code__file">send-message.sh</span>
              </div>
              <pre><span class="c-c"># Send a message via the REST API</span>
<span class="c-k">curl</span> https://api.yourcompany.com/v1/messages \\
  -H <span class="c-s">"Authorization: Bearer $API_KEY"</span> \\
  -d <span class="c-s">"to=+9779800000000"</span> \\
  -d <span class="c-s">"sender=YourBrand"</span> \\
  -d <span class="c-s">"body=Your appointment is confirmed"</span></pre>
            </div>
          </div>
        </section>

        <!-- Final CTA -->
        <section class="cta">
          <div class="cta__card reveal">
            <h2>Bring your communications together.</h2>
            <p>Register your company and get set up after a quick review.</p>
            <div class="cta__actions">
              <a class="btn btn--primary btn--lg" routerLink="/auth/register">
                Register company
              </a>
              <a class="btn btn--ghost btn--lg" routerLink="/auth/login">Log in</a>
            </div>
          </div>
        </section>
      </main>

      <!-- Footer -->
      <footer class="foot">
        <div class="foot__inner">
          <div class="foot__brand">
            <span class="brand__mark" aria-hidden="true">◈</span>
            <span>Telecom Console</span>
            <p>Operations for SMS, voice and missed-call.</p>
          </div>
          <div class="foot__cols">
            <div>
              <h4>Product</h4>
              <a href="#capabilities" (click)="go('capabilities', $event)">Platform</a>
              <a href="#preview" (click)="go('preview', $event)">Analytics</a>
              <a href="#security" (click)="go('security', $event)">Security</a>
            </div>
            <div>
              <h4>Solutions</h4>
              @for (s of solutions; track s.slug) {
                <a [routerLink]="['/solutions', s.slug]">{{ s.title }}</a>
              }
            </div>
            <div>
              <h4>Developers</h4>
              <a routerLink="/docs">Documentation</a>
              <a href="#developers" (click)="go('developers', $event)">API overview</a>
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
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
      }
      .lp {
        color-scheme: light;
        --ink: var(--mat-sys-on-surface);
        --muted: var(--mat-sys-on-surface-variant);
        --primary: var(--mat-sys-primary);
        --on-primary: var(--mat-sys-on-primary);
        --tertiary: var(--mat-sys-tertiary);
        --bg: var(--mat-sys-surface-container-lowest);
        --soft: var(--mat-sys-surface);
        --tint: var(--mat-sys-surface-container-low);
        --border: var(--mat-sys-outline-variant);
        --radius: 16px;
        --font: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto,
          Helvetica, Arial, sans-serif;
        --shadow-sm: 0 1px 2px rgba(16, 24, 32, 0.05);
        --shadow: 0 1px 2px rgba(16, 24, 32, 0.05),
          0 12px 28px -18px rgba(16, 24, 32, 0.25);
        font-family: var(--font);
        color: var(--ink);
        background: var(--bg);
        position: relative;
      }
      .lp::before {
        content: '';
        position: fixed;
        inset: 0 0 auto 0;
        height: 3px;
        z-index: 30;
        background: linear-gradient(
          90deg,
          var(--primary),
          color-mix(in srgb, var(--primary) 50%, var(--tertiary)),
          var(--tertiary)
        );
      }
      .lp a {
        text-decoration: none;
        color: inherit;
      }
      .section[id] {
        scroll-margin-top: 84px;
      }
      /* Accessible keyboard focus */
      .lp a:focus-visible,
      .btn:focus-visible {
        outline: 2px solid var(--primary);
        outline-offset: 3px;
        border-radius: 8px;
      }

      /* Buttons */
      .btn {
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
        font-weight: 550;
        font-size: 0.925rem;
        line-height: 1;
        padding: 0.6rem 1rem;
        border-radius: 10px;
        border: 1px solid transparent;
        transition: all 0.18s ease;
        cursor: pointer;
        white-space: nowrap;
      }
      .btn mat-icon {
        font-size: 1.05rem;
        width: 1.05rem;
        height: 1.05rem;
        transition: transform 0.18s ease;
      }
      .btn--lg {
        padding: 0.8rem 1.35rem;
        font-size: 1rem;
        border-radius: 12px;
      }
      .btn--primary {
        color: #ffffff;
        background: linear-gradient(
          135deg,
          color-mix(in srgb, var(--primary) 88%, #ffffff),
          var(--primary) 55%,
          color-mix(in srgb, var(--primary) 78%, #000000)
        );
        box-shadow: 0 1px 2px rgba(16, 24, 32, 0.12),
          0 8px 18px -10px color-mix(in srgb, var(--primary) 60%, transparent),
          inset 0 1px 0 rgba(255, 255, 255, 0.28);
        text-shadow: 0 1px 1px rgba(0, 0, 0, 0.18);
      }
      .btn--primary mat-icon {
        color: #ffffff;
      }
      .btn--primary:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 4px rgba(16, 24, 32, 0.14),
          0 14px 28px -10px color-mix(in srgb, var(--primary) 62%, transparent),
          inset 0 1px 0 rgba(255, 255, 255, 0.32);
      }
      .btn--primary:active {
        transform: translateY(0);
      }
      .btn--ghost {
        background: var(--bg);
        color: var(--ink);
        border-color: var(--border);
      }
      .btn--ghost:hover {
        background: var(--tint);
        border-color: color-mix(in srgb, var(--primary) 35%, var(--border));
      }
      .btn--ghost:hover mat-icon {
        transform: translateX(3px);
      }

      /* Nav */
      .nav {
        position: sticky;
        top: 0;
        z-index: 20;
        transition: background 0.25s ease, border-color 0.25s ease;
        border-bottom: 1px solid transparent;
      }
      .nav--scrolled {
        background: color-mix(in srgb, var(--bg) 82%, transparent);
        backdrop-filter: saturate(180%) blur(12px);
        border-bottom-color: var(--border);
      }
      .nav__inner {
        max-width: 1140px;
        margin: 0 auto;
        padding: 1rem clamp(1.1rem, 4vw, 2rem);
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
      }
      .brand__mark {
        color: var(--primary);
        font-size: 1.05rem;
      }
      .nav__links {
        display: flex;
        gap: 1.5rem;
        margin: 0 auto 0 1rem;
      }
      .nav__links a {
        position: relative;
        font-size: 0.925rem;
        color: var(--muted);
        transition: color 0.15s ease;
      }
      .nav__links a::after {
        content: '';
        position: absolute;
        left: 0;
        right: 100%;
        bottom: -5px;
        height: 2px;
        border-radius: 2px;
        background: var(--primary);
        transition: right 0.22s ease;
      }
      .nav__links a:hover {
        color: var(--primary);
      }
      .nav__links a:hover::after {
        right: 0;
      }
      .nav__actions {
        display: flex;
        align-items: center;
        gap: 0.6rem;
      }

      /* Nav dropdowns */
      .ddown {
        position: relative;
      }
      .ddown__btn {
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
      .ddown__btn:hover,
      .ddown__btn.is-open {
        color: var(--primary);
      }
      .ddown__btn mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        transition: transform 0.2s ease;
      }
      .ddown__btn.is-open mat-icon {
        transform: rotate(180deg);
      }
      .ddown__menu {
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
        gap: 0.1rem;
        animation: ddpop 0.16s ease;
      }
      @keyframes ddpop {
        from { opacity: 0; transform: translateY(-4px); }
        to { opacity: 1; transform: none; }
      }
      .ddown__item {
        display: grid;
        gap: 0.1rem;
        padding: 0.5rem 0.65rem;
        border-radius: 10px;
        color: var(--ink);
        transition: background 0.15s ease;
      }
      .ddown__item:hover {
        background: var(--tint);
      }
      .ddown__t {
        font-weight: 600;
        font-size: 0.9rem;
        display: inline-flex;
        align-items: center;
        gap: 0.4rem;
      }
      .ddown__d {
        font-size: 0.78rem;
        color: var(--muted);
      }
      .soon {
        font-size: 0.6rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: var(--primary);
        background: color-mix(in srgb, var(--primary) 12%, transparent);
        border-radius: 999px;
        padding: 0.05rem 0.4rem;
      }

      /* Layout primitives */
      .section {
        max-width: 1140px;
        margin: 0 auto;
        padding: clamp(3.5rem, 8vw, 6.5rem) clamp(1.1rem, 4vw, 2rem);
      }
      .section__head {
        max-width: 640px;
        margin: 0 auto 2.75rem;
        text-align: center;
      }
      .eyebrow {
        display: inline-flex;
        align-items: center;
        font-size: 0.72rem;
        font-weight: 650;
        letter-spacing: 0.09em;
        text-transform: uppercase;
        color: var(--primary);
        margin-bottom: 1rem;
        padding: 0.32rem 0.7rem;
        border-radius: 999px;
        background: color-mix(in srgb, var(--primary) 9%, transparent);
        border: 1px solid color-mix(in srgb, var(--primary) 18%, transparent);
      }
      h1 {
        margin: 0 0 1.1rem;
        font-size: clamp(2.4rem, 5.2vw, 3.6rem);
        line-height: 1.05;
        letter-spacing: -0.03em;
        font-weight: 700;
      }
      h2 {
        margin: 0 0 0.85rem;
        font-size: clamp(1.7rem, 3.2vw, 2.35rem);
        line-height: 1.12;
        letter-spacing: -0.025em;
        font-weight: 700;
      }
      h3 {
        margin: 0 0 0.4rem;
        font-size: 1.05rem;
        font-weight: 650;
      }
      .lead,
      .section__lead {
        color: var(--muted);
        font-size: 1.075rem;
        line-height: 1.65;
        margin: 0;
      }

      /* Hero */
      .hero {
        max-width: 1140px;
        margin: 0 auto;
        padding: clamp(2.5rem, 6vw, 4.5rem) clamp(1.1rem, 4vw, 2rem)
          clamp(2rem, 5vw, 3.5rem);
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: clamp(1.5rem, 4vw, 3rem);
        align-items: center;
        background:
          radial-gradient(58rem 30rem at 84% -12%,
            color-mix(in srgb, var(--primary) 13%, transparent), transparent 60%),
          linear-gradient(180deg,
            color-mix(in srgb, var(--primary) 4%, var(--bg)), var(--bg) 42%);
      }
      .hero__copy {
        max-width: 34rem;
      }
      .hero__cta {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem;
        margin-top: 1.6rem;
      }
      .hero__note {
        margin: 1rem 0 0;
        font-size: 0.85rem;
        color: var(--muted);
      }

      /* Product window */
      .window {
        border: 1px solid var(--border);
        border-radius: 16px;
        background: linear-gradient(180deg,
          color-mix(in srgb, var(--primary) 4%, var(--bg)), var(--bg) 30%);
        box-shadow: 0 1px 2px rgba(16, 24, 32, 0.06),
          0 30px 60px -34px rgba(16, 24, 32, 0.4),
          0 8px 20px -20px color-mix(in srgb, var(--primary) 50%, transparent);
        overflow: hidden;
        transform: perspective(1600px) rotateY(-7deg) rotateX(3deg) translateZ(0);
        transition: transform 0.5s cubic-bezier(0.2, 0.7, 0.2, 1),
          box-shadow 0.5s ease;
      }
      .window:hover {
        transform: perspective(1600px) rotateY(-2deg) rotateX(1deg) translateY(-4px);
        box-shadow: 0 2px 4px rgba(16, 24, 32, 0.07),
          0 40px 70px -34px rgba(16, 24, 32, 0.45),
          0 10px 24px -18px color-mix(in srgb, var(--primary) 55%, transparent);
      }
      .window__bar {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.65rem 0.85rem;
        border-bottom: 1px solid var(--border);
        background: var(--soft);
      }
      .dot {
        width: 9px;
        height: 9px;
        border-radius: 50%;
        background: var(--border);
      }
      .window__label,
      .code__file {
        margin-left: auto;
        font-size: 0.72rem;
        color: var(--muted);
      }
      .app {
        display: grid;
        grid-template-columns: 128px 1fr;
        min-height: 236px;
      }
      .app__side {
        border-right: 1px solid var(--border);
        padding: 0.8rem 0.6rem;
        background: var(--soft);
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
      }
      .app__brand {
        display: flex;
        align-items: center;
        gap: 0.35rem;
        font-weight: 700;
        font-size: 0.85rem;
        padding: 0.2rem 0.4rem 0.7rem;
      }
      .app__brand span {
        color: var(--primary);
      }
      .app__nav {
        display: flex;
        align-items: center;
        gap: 0.45rem;
        font-size: 0.78rem;
        color: var(--muted);
        padding: 0.4rem 0.45rem;
        border-radius: 8px;
      }
      .app__nav mat-icon {
        font-size: 15px;
        width: 15px;
        height: 15px;
        color: var(--muted);
      }
      .app__nav.is-active {
        background: color-mix(in srgb, var(--primary) 12%, transparent);
        color: var(--primary);
      }
      .app__nav.is-active mat-icon {
        color: var(--primary);
      }
      .app__main {
        padding: 0.95rem 1.05rem;
      }
      .app__head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 0.85rem;
      }
      .app__title {
        font-weight: 650;
        font-size: 0.95rem;
      }
      .app__sub {
        font-size: 0.72rem;
        color: var(--muted);
      }
      .pill {
        font-size: 0.68rem;
        font-weight: 600;
        color: var(--primary);
        background: color-mix(in srgb, var(--primary) 12%, transparent);
        padding: 0.15rem 0.5rem;
        border-radius: 999px;
      }
      .pill.soft {
        color: var(--muted);
        background: var(--tint);
      }
      .stats {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 0.55rem;
      }
      .stat {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 0.55rem 0.6rem;
        display: flex;
        flex-direction: column;
        gap: 0.15rem;
      }
      .stat__k {
        font-size: 0.66rem;
        color: var(--muted);
      }
      .stat__v {
        font-size: 1.02rem;
        font-weight: 700;
      }
      .stat__d {
        font-size: 0.64rem;
        color: var(--muted);
      }
      .stat__d.up {
        color: var(--primary);
      }
      .chart {
        border: 1px solid var(--border);
        border-radius: 10px;
        padding: 0.5rem;
        margin-top: 0.7rem;
      }
      .chart svg {
        width: 100%;
        height: 74px;
        display: block;
      }
      .spark-line {
        stroke-dasharray: 360;
        stroke-dashoffset: 360;
      }
      .reveal.is-in .spark-line {
        animation: draw 1.1s ease 0.3s forwards;
      }
      @keyframes draw {
        to {
          stroke-dashoffset: 0;
        }
      }

      /* Cards grid */
      .cards {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        gap: 1rem;
      }
      .card {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem 1.35rem;
        box-shadow: var(--shadow-sm);
        transition: transform 0.2s ease, box-shadow 0.2s ease,
          border-color 0.2s ease;
      }
      .card:hover {
        transform: translateY(-4px);
        box-shadow: var(--shadow);
        border-color: color-mix(in srgb, var(--primary) 30%, var(--border));
      }
      .card__icon {
        width: 42px;
        height: 42px;
        border-radius: 11px;
        display: grid;
        place-items: center;
        margin-bottom: 0.95rem;
        color: var(--primary);
        background: linear-gradient(135deg,
          color-mix(in srgb, var(--primary) 16%, transparent),
          color-mix(in srgb, var(--tertiary) 12%, transparent));
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.5);
        transition: transform 0.2s ease;
      }
      .card:hover .card__icon {
        transform: scale(1.06);
      }
      .card p {
        margin: 0;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.55;
      }

      /* Split sections */
      .split {
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: clamp(2rem, 5vw, 4rem);
        align-items: center;
      }
      .ticks {
        list-style: none;
        margin: 1.4rem 0 0;
        padding: 0;
        display: flex;
        flex-direction: column;
        gap: 0.7rem;
      }
      .ticks li {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        color: var(--ink);
        font-size: 0.96rem;
      }
      .ticks mat-icon {
        font-size: 18px;
        width: 18px;
        height: 18px;
        color: var(--on-primary);
        background: var(--primary);
        border-radius: 50%;
        padding: 2px;
      }
      .panel {
        background: var(--bg);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        box-shadow: var(--shadow);
        padding: 1.25rem 1.35rem 1.5rem;
      }
      .panel__head {
        display: flex;
        align-items: center;
        justify-content: space-between;
        font-size: 0.85rem;
        font-weight: 600;
        color: var(--ink);
        margin-bottom: 1.25rem;
      }
      .bars {
        display: grid;
        grid-template-columns: repeat(4, 1fr);
        align-items: end;
        gap: 0.9rem;
        height: 150px;
      }
      .bar {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: flex-end;
        height: 100%;
        gap: 0.5rem;
      }
      .bar i {
        width: 100%;
        border-radius: 8px 8px 4px 4px;
        background: var(--primary);
        display: block;
        transform: scaleY(0);
        transform-origin: bottom;
        transition: transform 0.7s cubic-bezier(0.2, 0.7, 0.2, 1);
      }
      .reveal.is-in .bar i {
        transform: scaleY(1);
      }
      .bar:nth-child(2) i { transition-delay: 0.08s; }
      .bar:nth-child(3) i { transition-delay: 0.16s; }
      .bar:nth-child(4) i { transition-delay: 0.24s; }
      .bar.alt i {
        background: var(--tertiary);
      }
      .bar span {
        font-size: 0.72rem;
        color: var(--muted);
      }

      /* Feature grid */
      .grid-3 {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1rem;
      }
      .feature {
        background: var(--soft);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 1.5rem 1.4rem;
        transition: transform 0.2s ease, border-color 0.2s ease;
      }
      .feature:hover {
        transform: translateY(-3px);
        border-color: color-mix(in srgb, var(--primary) 30%, var(--border));
      }
      .feature > mat-icon {
        color: var(--primary);
        margin-bottom: 0.7rem;
      }
      .feature p {
        margin: 0;
        color: var(--muted);
        font-size: 0.9rem;
        line-height: 1.55;
      }

      /* Code card */
      .code {
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: var(--shadow);
        border: 1px solid var(--border);
      }
      .code__bar {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        padding: 0.6rem 0.8rem;
        background: var(--soft);
        border-bottom: 1px solid var(--border);
      }
      .code pre {
        margin: 0;
        padding: 1.1rem 1.2rem;
        background: var(--tint);
        color: var(--ink);
        font-size: 0.8rem;
        line-height: 1.7;
        font-family: ui-monospace, 'SFMono-Regular', Menlo, Consolas, monospace;
        overflow-x: auto;
      }
      .c-c { color: var(--muted); }
      .c-k { color: var(--primary); font-weight: 600; }
      .c-s { color: var(--tertiary); }

      /* Final CTA */
      .cta {
        max-width: 1140px;
        margin: 0 auto;
        padding: clamp(1rem, 3vw, 2rem) clamp(1.1rem, 4vw, 2rem)
          clamp(3.5rem, 7vw, 6rem);
      }
      .cta__card {
        text-align: center;
        padding: clamp(2.5rem, 6vw, 4rem) 1.5rem;
        border-radius: 24px;
        border: 1px solid color-mix(in srgb, var(--primary) 16%, var(--border));
        background: radial-gradient(44rem 22rem at 50% -25%,
          color-mix(in srgb, var(--primary) 14%, transparent), transparent 62%),
          linear-gradient(180deg,
            color-mix(in srgb, var(--primary) 5%, var(--bg)),
            var(--tint));
        box-shadow: 0 1px 2px rgba(16, 24, 32, 0.05),
          0 30px 60px -40px color-mix(in srgb, var(--primary) 55%, transparent);
      }
      .cta__card h2 {
        margin-bottom: 0.5rem;
      }
      .cta__card p {
        color: var(--muted);
        margin: 0 auto 1.6rem;
        max-width: 34rem;
      }
      .cta__actions {
        display: flex;
        gap: 0.75rem;
        justify-content: center;
        flex-wrap: wrap;
      }

      /* Footer */
      .foot {
        border-top: 1px solid var(--border);
        background: var(--soft);
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
      .foot__brand .brand__mark {
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

      /* Scroll-reveal motion */
      .reveal {
        opacity: 0;
        transform: translateY(16px);
        transition: opacity 0.6s ease, transform 0.6s cubic-bezier(0.2, 0.7, 0.2, 1);
      }
      .reveal.is-in {
        opacity: 1;
        transform: none;
      }

      /* Responsive */
      @media (max-width: 900px) {
        .hero,
        .split {
          grid-template-columns: 1fr;
        }
        .hero__copy {
          max-width: none;
        }
        .cards {
          grid-template-columns: repeat(2, 1fr);
        }
        .grid-3 {
          grid-template-columns: 1fr;
        }
        .nav__links {
          display: none;
        }
      }
      @media (max-width: 560px) {
        .cards {
          grid-template-columns: 1fr;
        }
        .stats {
          grid-template-columns: 1fr;
        }
        .brand__name {
          display: none;
        }
      }
      @media (prefers-reduced-motion: reduce) {
        .reveal {
          opacity: 1;
          transform: none;
          transition: none;
        }
        .reveal.is-in .bar i {
          transition: none;
        }
        .bar i {
          transform: scaleY(1);
        }
        .spark-line {
          stroke-dashoffset: 0;
        }
        .window,
        .btn,
        .card,
        .feature,
        .card__icon,
        .btn mat-icon {
          transition: none;
        }
        .window {
          transform: none;
        }
        .window {
          transform: none;
        }
      }
    `,
  ],
})
export class LandingComponent implements AfterViewInit {
  private readonly host = inject(ElementRef<HTMLElement>);

  /** Solutions shown in the nav dropdown + footer (shared source). */
  readonly solutions = SOLUTIONS;

  /** Toggles the subtle nav blur/border once the page is scrolled. */
  readonly scrolled = signal(false);

  /** Which nav dropdown is open ('sol' | 'dev' | null). */
  readonly menu = signal<string | null>(null);

  toggleMenu(name: string, ev: Event): void {
    ev.stopPropagation();
    this.menu.set(this.menu() === name ? null : name);
  }

  closeMenu(): void {
    this.menu.set(null);
  }

  @HostListener('document:click')
  onDocClick(): void {
    this.menu.set(null);
  }

  @HostListener('document:keydown.escape')
  onEsc(): void {
    this.menu.set(null);
  }

  @HostListener('window:scroll')
  onScroll(): void {
    this.scrolled.set(window.scrollY > 8);
  }

  ngAfterViewInit(): void {
    const root = this.host.nativeElement as HTMLElement;
    const els = Array.from(root.querySelectorAll<HTMLElement>('.reveal'));
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    // Reveal immediately if motion is reduced or IO is unavailable.
    if (reduce || typeof IntersectionObserver === 'undefined') {
      els.forEach((el) => el.classList.add('is-in'));
      return;
    }

    const io = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add('is-in');
            io.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.14, rootMargin: '0px 0px -8% 0px' },
    );
    els.forEach((el) => io.observe(el));
  }

  /** Smooth in-page scroll for nav/footer anchors (honors reduced motion). */
  go(id: string, ev: Event): void {
    ev.preventDefault();
    const target = (this.host.nativeElement as HTMLElement).querySelector(
      '#' + id,
    );
    if (!target) return;
    const reduce =
      typeof window.matchMedia === 'function' &&
      window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    target.scrollIntoView({
      behavior: reduce ? 'auto' : 'smooth',
      block: 'start',
    });
  }
}
