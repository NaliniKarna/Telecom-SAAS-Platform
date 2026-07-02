import { Component, inject } from '@angular/core';
import { MatCardModule } from '@angular/material/card';

import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-admin-home',
  standalone: true,
  imports: [MatCardModule],
  template: `
    <header class="page-header">
      <h1>Platform administration</h1>
      <p>Super-admin landing. Companies, users, and system stats live here.</p>
    </header>

    <div class="grid">
      <mat-card appearance="outlined">
        <mat-card-header>
          <mat-card-title>Signed in as</mat-card-title>
        </mat-card-header>
        <mat-card-content>
          <p>{{ auth.user()?.email }}</p>
          <p class="muted">Platform scope · super_admin</p>
        </mat-card-content>
      </mat-card>
    </div>
  `,
  styles: [
    `
      .page-header {
        margin-bottom: 1.5rem;
      }
      .page-header h1 {
        font: var(--mat-sys-headline-medium);
        margin: 0 0 0.25rem;
      }
      .page-header p {
        color: var(--mat-sys-on-surface-variant);
        margin: 0;
      }
      .grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
        gap: 1rem;
      }
      .muted {
        color: var(--mat-sys-on-surface-variant);
      }
    `,
  ],
})
export class AdminHomeComponent {
  readonly auth = inject(AuthService);
}