import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';

import { Permission, RoleName } from '../constants/rbac.constants';
import { AuthService } from '../services/auth.service';

/**
 * Role guard factory. Pass allowed roles; super admin always passes.
 * Usage: `canActivate: [roleGuard([RoleName.SuperAdmin])]`
 */
export function roleGuard(allowed: RoleName[]): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);

    if (auth.isSuperAdmin() || allowed.some((r) => auth.hasRole(r))) {
      return true;
    }
    return router.createUrlTree(['/forbidden']);
  };
}

/**
 * Permission guard factory. User must hold AT LEAST ONE of the listed
 * permissions (super admin bypasses).
 * Usage: `canActivate: [permissionGuard([Permission.CompanyRead])]`
 */
export function permissionGuard(required: Permission[]): CanActivateFn {
  return () => {
    const auth = inject(AuthService);
    const router = inject(Router);

    if (auth.hasAnyPermission(required)) {
      return true;
    }
    return router.createUrlTree(['/forbidden']);
  };
}

/**
 * Root redirect: sends the authenticated user to their role-based landing
 * route. Used on the index path where `redirectTo` can't be computed.
 */
export const landingRedirectGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return router.createUrlTree([auth.landingRoute()]);
};
