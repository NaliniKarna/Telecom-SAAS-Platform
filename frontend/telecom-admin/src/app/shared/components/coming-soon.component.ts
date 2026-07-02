import { Component, Input } from '@angular/core';
import { MatCardModule } from '@angular/material/card';
import { MatIconModule } from '@angular/material/icon';

@Component({
  selector: 'app-coming-soon',
  standalone: true,
  imports: [MatCardModule, MatIconModule],
  template: `
    <div class="coming-soon">
      <mat-icon class="coming-soon__icon">{{ icon }}</mat-icon>
      <h1>{{ title }}</h1>
      <p>{{ message }}</p>
    </div>
  `,
  styles: [
    `
      .coming-soon {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
        gap: 0.5rem;
        padding: 4rem 1rem;
        color: var(--mat-sys-on-surface-variant);
      }
      .coming-soon__icon {
        font-size: 3rem;
        width: 3rem;
        height: 3rem;
        opacity: 0.6;
      }
      .coming-soon h1 {
        font: var(--mat-sys-headline-small);
        color: var(--mat-sys-on-surface);
        margin: 0.5rem 0 0;
      }
      .coming-soon p {
        margin: 0;
        max-width: 28rem;
      }
    `,
  ],
})
export class ComingSoonComponent {
  @Input() title = 'Coming soon';
  @Input() icon = 'construction';
  @Input() message = 'This module is on the way.';
}
