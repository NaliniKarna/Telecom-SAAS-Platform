import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';

import { environment } from '../../../environments/environment';
import { TokenStorageService } from '../services/token-storage.service';

/** Endpoints that must never receive the access token. */
const SKIP_AUTH = ['/auth/login', '/auth/refresh', '/auth/forgot-password'];

/**
 * Attaches the bearer access token to outgoing API requests.
 * Skips auth endpoints and any non-API (e.g. asset) requests.
 */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const tokens = inject(TokenStorageService);

  const isApi = req.url.startsWith(environment.apiBaseUrl);
  const isSkipped = SKIP_AUTH.some((path) => req.url.includes(path));
  const accessToken = tokens.accessToken;

  if (isApi && !isSkipped && accessToken) {
    req = req.clone({
      setHeaders: { Authorization: `Bearer ${accessToken}` },
    });
  }
  return next(req);
};
