import {
  Component,
  inject,
  signal,
  viewChild,
} from '@angular/core';
import { BreakpointObserver, Breakpoints } from '@angular/cdk/layout';
import { MatSidenavModule, MatSidenav } from '@angular/material/sidenav';
import { RouterOutlet } from '@angular/router';
import { toSignal } from '@angular/core/rxjs-interop';
import { map } from 'rxjs';

import { SidebarComponent } from '../components/sidebar/sidebar.component';
import { TopbarComponent } from '../components/topbar/topbar.component';

/**
 * Authenticated app shell. Sidenav is persistent ('side') on desktop and
 * overlay ('over') on mobile, driven by the CDK BreakpointObserver.
 */
@Component({
  selector: 'app-main-layout',
  standalone: true,
  imports: [
    MatSidenavModule,
    RouterOutlet,
    SidebarComponent,
    TopbarComponent,
  ],
  template: `
    <app-topbar (toggleSidenav)="toggleSidenav()" />

    <mat-sidenav-container class="layout">
      <mat-sidenav
        #sidenav
        class="layout__sidenav"
        [mode]="isHandset() ? 'over' : 'side'"
        [opened]="!isHandset()"
      >
        <app-sidebar />
      </mat-sidenav>

      <mat-sidenav-content class="layout__content">
        <main class="layout__main">
          <router-outlet />
        </main>
      </mat-sidenav-content>
    </mat-sidenav-container>
  `,
  styles: [
    `
      .layout {
        height: calc(100vh - 64px);
        background: var(--mat-sys-surface);
      }
      .layout__sidenav {
        width: 248px;
        border-right: 1px solid var(--mat-sys-outline-variant);
        background: var(--mat-sys-surface-container-low);
      }
      .layout__main {
        padding: 1.5rem;
        max-width: 1280px;
        margin: 0 auto;
      }
    `,
  ],
})
export class MainLayoutComponent {
  private readonly breakpoints = inject(BreakpointObserver);
  readonly sidenav = viewChild<MatSidenav>('sidenav');

  readonly isHandset = toSignal(
    this.breakpoints
      .observe(Breakpoints.Handset)
      .pipe(map((result) => result.matches)),
    { initialValue: false },
  );

  toggleSidenav(): void {
    void this.sidenav()?.toggle();
  }
}
