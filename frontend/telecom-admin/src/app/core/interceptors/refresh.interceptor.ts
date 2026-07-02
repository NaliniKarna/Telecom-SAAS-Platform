import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import {
  BehaviorSubject,
  catchError,
  filter,
  switchMap,
  take,
  throwError,
} from 'rxjs';

import { environment } from '../../../environments/environment';
import { AuthService } from '../services/auth.service';
import { TokenStorageService } from '../services/token-storage.service';

/**
 * Module-level refresh coordination. When a 401 hits, the first request
 * triggers a single refresh; concurrent 401s queue and replay once the new
 * token lands. Prevents a refresh storm.
 */
let isRefreshing = false;
const refreshedToken$ = new BehaviorSubject<string | null>(null);

const DONT_RETRY = ['/auth/login', '/auth/refresh', '/auth/logout'];

export const refreshInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const tokens = inject(TokenStorageService);

  const isApi = req.url.startsWith(environment.apiBaseUrl);
  const skipRetry = DONT_RETRY.some((p) => req.url.includes(p));

  return next(req).pipe(
    catchError((error: unknown) => {
      const is401 =
        error instanceof HttpErrorResponse && error.status === 401;

      if (!is401 || !isApi || skipRetry || !tokens.refreshToken) {
        return throwError(() => error);
      }

      if (isRefreshing) {
        // Wait for the in-flight refresh, then replay with the new token.
        return refreshedToken$.pipe(
          filter((t): t is string => t !== null),
          take(1),
          switchMap((token) =>
            next(
              req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }),
            ),
          ),
        );
      }

      isRefreshing = true;
      refreshedToken$.next(null);

      return auth.refresh().pipe(
        switchMap((res) => {
          isRefreshing = false;
          refreshedToken$.next(res.access_token);
          return next(
            req.clone({
              setHeaders: { Authorization: `Bearer ${res.access_token}` },
            }),
          );
        }),
        catchError((refreshErr) => {
          isRefreshing = false;
          auth.expireSession();   // was: auth.clearSession();
          return throwError(() => refreshErr);
        }),
      );
    }),
  );
};
