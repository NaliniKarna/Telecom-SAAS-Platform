import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';

@Component({
  selector: 'app-auth-layout',
  standalone: true,
  imports: [RouterOutlet],
  template: `
    <div class="auth-shell">
      <div class="auth-panel">
        <div class="auth-brand">
          <span class="auth-brand__mark">◈</span>
          <span class="auth-brand__name">Telecom Console</span>
        </div>
        <router-outlet />
      </div>
    </div>
  `,
  styles: [
    `
      .auth-shell {
        min-height: 100vh;
        display: grid;
        place-items: center;
        padding: 1.5rem;
        background:
          radial-gradient(
            120% 120% at 100% 0%,
            color-mix(in srgb, var(--mat-sys-primary) 12%, transparent),
            transparent 55%
          ),
          var(--mat-sys-surface);
      }
      .auth-panel {
        width: 100%;
        max-width: 26rem;
        background: var(--mat-sys-surface-container-low);
        border: 1px solid var(--mat-sys-outline-variant);
        border-radius: 18px;
        padding: 2.25rem;
        box-shadow: 0 18px 48px -28px rgba(0, 0, 0, 0.5);
      }
      .auth-brand {
        display: flex;
        align-items: center;
        gap: 0.6rem;
        margin-bottom: 1.75rem;
      }
      .auth-brand__mark {
        color: var(--mat-sys-primary);
        font-size: 1.5rem;
        line-height: 1;
      }
      .auth-brand__name {
        font: var(--mat-sys-title-medium);
        letter-spacing: 0.02em;
      }
    `,
  ],
})
export class AuthLayoutComponent {}
