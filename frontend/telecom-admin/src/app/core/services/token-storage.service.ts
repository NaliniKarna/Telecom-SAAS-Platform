import { Injectable } from '@angular/core';

/**
 * Single owner of token persistence. Isolating this means the storage
 * mechanism (localStorage now, httpOnly cookies later) can change without
 * touching AuthService.
 *
 * Note: localStorage is used for the foundation. For higher security,
 * migrate refresh tokens to httpOnly cookies on the API side.
 */
@Injectable({ providedIn: 'root' })
export class TokenStorageService {
  private readonly ACCESS_KEY = 'tlk.access';
  private readonly REFRESH_KEY = 'tlk.refresh';

  get accessToken(): string | null {
    return localStorage.getItem(this.ACCESS_KEY);
  }

  get refreshToken(): string | null {
    return localStorage.getItem(this.REFRESH_KEY);
  }

  setTokens(access: string, refresh: string): void {
    localStorage.setItem(this.ACCESS_KEY, access);
    localStorage.setItem(this.REFRESH_KEY, refresh);
  }

  clear(): void {
    localStorage.removeItem(this.ACCESS_KEY);
    localStorage.removeItem(this.REFRESH_KEY);
  }

  /** Decode JWT payload without verifying (client-side hints only). */
  decode<T = Record<string, unknown>>(token: string): T | null {
    try {
      const payload = token.split('.')[1];
      return JSON.parse(atob(payload.replace(/-/g, '+').replace(/_/g, '/')));
    } catch {
      return null;
    }
  }

  isExpired(token: string, skewSeconds = 10): boolean {
    const payload = this.decode<{ exp?: number }>(token);
    if (!payload?.exp) return true;
    return payload.exp * 1000 <= Date.now() + skewSeconds * 1000;
  }
}
