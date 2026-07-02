import { Component } from '@angular/core';
import { RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';

@Component({
  selector: 'app-forbidden',
  standalone: true,
  imports: [RouterLink, MatButtonModule],
  template: `
    <div class="forbidden">
      <p class="forbidden__code">403</p>
      <h1>No access here</h1>
      <p class="forbidden__msg">
        Your account doesn't have permission to view this page. If you think
        this is a mistake, contact your company administrator.
      </p>
      <a mat-flat-button color="primary" routerLink="/dashboard">
        Back to dashboard
      </a>
    </div>
  `,
  styles: [
    `
      .forbidden {
        min-height: 60vh;
        display: grid;
        place-content: center;
        text-align: center;
        gap: 0.5rem;
      }
      .forbidden__code {
        font: var(--mat-sys-display-medium);
        color: var(--mat-sys-primary);
        margin: 0;
      }
      .forbidden__msg {
        max-width: 28rem;
        color: var(--mat-sys-on-surface-variant);
      }
    `,
  ],
})
export class ForbiddenComponent {}
