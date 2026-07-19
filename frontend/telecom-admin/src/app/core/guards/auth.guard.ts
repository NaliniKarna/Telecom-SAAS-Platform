import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { AuthService } from '../services/auth.service';

/** Blocks routes unless the user is authenticated; redirects to login. */
export const authGuard: CanActivateFn = (_route, state) => {
  const auth = inject(AuthService);
  const router = inject(Router);

  if (auth.isAuthenticated()) {
    return true;
  }
  return router.createUrlTree(['/auth/login'], {
    queryParams: { returnUrl: state.url },
  });
};

/** Inverse guard: keeps authenticated users out of login/public pages,
 * sending them to their role-specific landing (super admin -> /admin). */
export const guestGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.isAuthenticated()
    ? router.createUrlTree([auth.landingRoute()])
    : true;
};

/**
 * Root ("/") entry decision. Unauthenticated visitors see the public landing
 * page; authenticated users are sent straight to their role-based app landing.
 * This makes the landing page the public entry point without touching the
 * login flow.
 */
export const rootEntryGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);

  return auth.isAuthenticated()
    ? router.createUrlTree([auth.landingRoute()])
    : router.createUrlTree(['/landing']);
};