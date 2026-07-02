import { Component, inject, OnInit, signal } from '@angular/core';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { AuthService } from '../../core/services/auth.service';

type VerifyState = 'verifying' | 'success' | 'error' | 'missing';

@Component({
  selector: 'app-verify-email',
  standalone: true,
  imports: [RouterLink, MatButtonModule, MatProgressBarModule],
  template: `
    <h1 class="ve__title">Email verification</h1>

    @switch (state()) {
      @case ('verifying') {
        <mat-progress-bar mode="indeterminate" />
        <p class="ve__msg">Verifying your email…</p>
      }
      @case ('success') {
        <p class="ve__msg ve__ok">Your email is verified. You're all set.</p>
        <a mat-flat-button color="primary" routerLink="/auth/login">
          Continue to sign in
        </a>
      }
      @case ('missing') {
        <p class="ve__msg ve__err">
          This verification link is invalid or incomplete.
        </p>
        <a mat-stroked-button routerLink="/auth/login">Back to sign in</a>
      }
      @case ('error') {
        <p class="ve__msg ve__err">
          This link is invalid or has expired. Sign in and request a new one.
        </p>
        <a mat-stroked-button routerLink="/auth/login">Back to sign in</a>
      }
    }
  `,
  styles: [
    `
      .ve__title {
        font: var(--mat-sys-headline-small);
        margin: 0 0 1rem;
      }
      .ve__msg {
        margin: 1rem 0 1.25rem;
        color: var(--mat-sys-on-surface-variant);
      }
      .ve__ok {
        color: var(--mat-sys-primary);
      }
      .ve__err {
        color: var(--mat-sys-error);
      }
    `,
  ],
})
export class VerifyEmailComponent implements OnInit {
  private readonly auth = inject(AuthService);
  private readonly route = inject(ActivatedRoute);

  readonly state = signal<VerifyState>('verifying');

  ngOnInit(): void {
    const token = this.route.snapshot.queryParamMap.get('token');
    if (!token) {
      this.state.set('missing');
      return;
    }
    this.auth.verifyEmail(token).subscribe({
      next: () => this.state.set('success'),
      error: () => this.state.set('error'),
    });
  }
}