import { computed, inject, Injectable, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, switchMap, tap } from 'rxjs';

import { environment } from '../../../environments/environment';
import { Permission, RoleName } from '../constants/rbac.constants';
import {
  CompanyRegistrationRequest,
  CurrentUser,
  LoginRequest,
  RegistrationResult,
  TokenResponse,
} from '../models/auth.models';
import { NotificationService } from './notification.service';
import { TokenStorageService } from './token-storage.service';

/**
 * Owns authentication state via signals. Components read `user`, `isAuthenticated`,
 * and the permission helpers reactively. This is the single source of truth for
 * "who is the current user and what may they do".
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private readonly http = inject(HttpClient);
  private readonly router = inject(Router);
  private readonly tokens = inject(TokenStorageService);
  private readonly notify = inject(NotificationService);

  private readonly baseUrl = `${environment.apiBaseUrl}/auth`;

  // Proactive-renewal timer handle (browser setTimeout id).
  private renewTimer: ReturnType<typeof setTimeout> | null = null;
  // Refresh this many ms before the access token's exp.
  private readonly RENEW_SKEW_MS = 60_000;

  // --- state ---------------------------------------------------------------
  private readonly _user = signal<CurrentUser | null>(null);
  private readonly _initialized = signal(false);

  /** The current user, or null when unauthenticated. */
  readonly user = this._user.asReadonly();
  /** True once the initial session bootstrap has completed. */
  readonly initialized = this._initialized.asReadonly();
  readonly isAuthenticated = computed(() => this._user() !== null);
  readonly roles = computed(() => this._user()?.roles ?? []);
  readonly permissions = computed(() => this._user()?.permissions ?? []);
  readonly isSuperAdmin = computed(() =>
    this.roles().includes(RoleName.SuperAdmin),
  );

  // --- session bootstrap ---------------------------------------------------
  /**
   * Restore the session on app start. If an access token exists, fetch the
   * current user; the interceptor handles refresh if the token is stale.
   * Always resolves (never rejects) so APP_INITIALIZER can proceed.
   */
  bootstrap(): Promise<void> {
    return new Promise((resolve) => {
      if (!this.tokens.accessToken) {
        this._initialized.set(true);
        resolve();
        return;
      }
      this.fetchMe().subscribe({
        next: () => {
          this.scheduleRenewal();
          this._initialized.set(true);
          resolve();
        },
        error: () => {
          this.tokens.clear();
          this._user.set(null);
          this._initialized.set(true);
          resolve();
        },
      });
    });
  }

  // --- auth operations -----------------------------------------------------
  login(credentials: LoginRequest): Observable<CurrentUser> {
    return this.http
      .post<TokenResponse>(`${this.baseUrl}/login`, credentials)
      .pipe(
        tap((res) =>
          this.tokens.setTokens(res.access_token, res.refresh_token),
        ),
        tap(() => this.scheduleRenewal()),
        // Only complete once the user profile is loaded, so guards that read
        // the `user` signal see an authenticated session before navigation.
        switchMap(() => this.fetchMe()),
      );
  }

  fetchMe(): Observable<CurrentUser> {
    return this.http
      .get<CurrentUser>(`${this.baseUrl}/me`)
      .pipe(tap((u) => this._user.set(u)));
  }

  refresh(): Observable<TokenResponse> {
    return this.http
      .post<TokenResponse>(`${this.baseUrl}/refresh`, {
        refresh_token: this.tokens.refreshToken,
      })
      .pipe(
        tap((res) => this.tokens.setTokens(res.access_token, res.refresh_token)),
        tap(() => this.scheduleRenewal()),
      );
  }

  /** Logout: best-effort server revoke, then clear local state and return to
   * the public landing page. */
  logout(): void {
    const refresh_token = this.tokens.refreshToken;
    if (refresh_token) {
      this.http
        .post(`${this.baseUrl}/logout`, { refresh_token })
        .subscribe({ error: () => void 0 });
    }
    this.clearSession();
    void this.router.navigate(['/landing']);
  }

  clearSession(): void {
    this.cancelRenewal();
    this.tokens.clear();
    this._user.set(null);
  }

  // --- proactive token renewal --------------------------------------------
  /**
   * Schedule a refresh shortly before the access token expires. The refresh
   * interceptor remains the reactive safety net (e.g. after laptop sleep when
   * a scheduled timer was suspended); this just avoids the user eating a
   * failed-then-retried request at every expiry.
   */
  private scheduleRenewal(): void {
    this.cancelRenewal();
    const token = this.tokens.accessToken;
    if (!token) return;

    const payload = this.tokens.decode<{ exp?: number }>(token);
    if (!payload?.exp) return;

    const fireInMs = payload.exp * 1000 - Date.now() - this.RENEW_SKEW_MS;
    // If already within the skew window, renew on the next tick.
    const delay = Math.max(fireInMs, 0);

    this.renewTimer = setTimeout(() => {
      // Only renew if still authenticated and a refresh token exists.
      if (!this.tokens.refreshToken || !this._user()) return;
      this.refresh().subscribe({
        // On failure the interceptor / expireSession path handles cleanup.
        error: () => void 0,
      });
    }, delay);
  }

  private cancelRenewal(): void {
    if (this.renewTimer !== null) {
      clearTimeout(this.renewTimer);
      this.renewTimer = null;
    }
  }

  // --- session expiration --------------------------------------------------
  /**
   * Involuntary end of session (refresh ultimately failed / token revoked).
   * Distinct from logout(): notifies the user and preserves returnUrl so they
   * land back where they were after signing in again.
   */
  expireSession(): void {
    // Avoid duplicate handling if multiple requests fail at once.
    if (!this._user() && !this.tokens.refreshToken) return;
    this.clearSession();
    this.notify.info('Your session expired — please sign in again.');
    const returnUrl = this.router.url;
    void this.router.navigate(['/auth/login'], {
      queryParams: returnUrl && returnUrl !== '/' ? { returnUrl } : {},
    });
  }

  // --- password recovery ---------------------------------------------------
  /**
   * Request a reset email. Sent with X-Silent-Error so the error interceptor
   * doesn't toast — the backend response is intentionally uniform.
   */
  forgotPassword(email: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.baseUrl}/forgot-password`,
      { email },
      { headers: { 'X-Silent-Error': 'true' } },
    );
  }

  resetPassword(token: string, newPassword: string): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/reset-password`, {
      token,
      new_password: newPassword,
    });
  }

  // --- email verification --------------------------------------------------
  /** True when a user is loaded and their email is verified. */
  readonly isEmailVerified = computed(
    () => this._user()?.is_email_verified ?? false,
  );

  verifyEmail(token: string): Observable<void> {
    return this.http.post<void>(`${this.baseUrl}/verify-email`, { token });
  }

  /**
   * Public company self-registration. Posts to /registration (not /auth): the
   * backend creates a pending-approval company + a pending company_admin and
   * emails a verification link. No session is created — the user verifies their
   * email, then a super admin approves before they can sign in.
   */
  registerCompany(payload: CompanyRegistrationRequest): Observable<RegistrationResult> {
    return this.http.post<RegistrationResult>(
      `${environment.apiBaseUrl}/registration`,
      payload,
    );
  }

  resendVerification(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${this.baseUrl}/resend-verification`,
      {},
    );
  }

  // --- authorization helpers ----------------------------------------------
  hasPermission(permission: Permission): boolean {
    if (this.isSuperAdmin()) return true;
    return this.permissions().includes(permission);
  }

  hasAnyPermission(permissions: Permission[]): boolean {
    if (this.isSuperAdmin()) return true;
    return permissions.some((p) => this.permissions().includes(p));
  }

  hasRole(role: RoleName): boolean {
    return this.roles().includes(role);
  }

  /**
   * Role-based landing path used after login and for the root redirect.
   * Super admins land on the platform admin area; everyone else on the
   * standard dashboard. Authoritative — derived from the loaded user's roles,
   * never from client input.
   */
  landingRoute(): string {
    if (this.isSuperAdmin()) return '/admin';
    return '/dashboard';
  }
}