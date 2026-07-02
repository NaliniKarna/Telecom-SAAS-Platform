# Telecom Console — Angular 20 Foundation

The frontend foundation for the multi-tenant telecom SaaS platform. Standalone
components, signals, Angular Material 20, functional guards and interceptors.
No feature modules yet — this is the verified base they plug into.

## Verified

- **Production build**: passes (`ng build` -> ~458 kB initial / 121 kB gzip).
- **Browser interaction (Playwright, 13/13)**: unauthenticated redirect, login
  form + validation, login -> dashboard, authenticated shell, permission-
  filtered sidebar (a company_admin sees Companies/Users/API Keys but not
  Audit Logs), guestGuard, and the 403 page.

## Architecture

### 1. Folder structure (layer-first)
    src/app/
      core/          singletons, app-wide concerns
        constants/   rbac.constants.ts (roles + permission catalog)
        models/      auth.models.ts (API DTOs)
        services/    auth, token-storage, notification
        guards/      auth.guard (auth/guest), rbac.guard (role/permission)
        interceptors/ auth, refresh, error
      shared/
        directives/  has-permission.directive (*appHasPermission)
      layout/
        auth-layout/    centered shell (login)
        main-layout/    responsive sidenav shell (authenticated)
        components/      sidebar (permission-filtered), topbar
        navigation.ts    nav definition, permission-gated
      features/      dashboard, auth (login), errors (403)
      environments/  dev + prod API base URLs

### 2 & 3. Core / Shared strategy
Angular 20 is module-free. "Core" = root-provided singletons
(providedIn: 'root'). "Shared" = standalone components/directives imported
where needed. No CoreModule/SharedModule NgModules.

### 4. AuthService (signals)
Single source of truth for the session: user, isAuthenticated, isSuperAdmin,
roles, permissions as signals, plus hasPermission/hasAnyPermission/hasRole.
Session restored on start via provideAppInitializer(bootstrap). login() chains
fetchMe() so the user signal is set BEFORE navigation — guards never see a
half-authenticated state (this was a real race, caught and fixed in testing).

### 5. HTTP interceptors (functional, ordered)
1. authInterceptor — attaches bearer token (skips auth endpoints/non-API).
2. refreshInterceptor — on 401, single refresh + queues concurrent requests,
   replays with new token; clears session on refresh failure.
3. errorInterceptor — maps API error envelope to notifications + typed error;
   respects X-Silent-Error header.

### 6. Route guards (functional)
authGuard / guestGuard (with returnUrl capture); roleGuard([...]) /
permissionGuard([...]) factory guards with super-admin bypass -> /forbidden.

### 7. Layout architecture
AuthLayout centers public pages. MainLayout is a responsive CDK sidenav (side
on desktop, over on mobile via BreakpointObserver), composing a
permission-filtered Sidebar and a Topbar with user menu.

### 8. Theme
Intentional: cyan "signal" primary + orange tertiary, color-scheme: light dark
(follows OS), snackbar accents on system tokens, reduced-motion honored.
Material icons bundled locally (material-icons package) — renders fully offline,
no CDN dependency.

### 9. State management
Signals are primary: auth state + derivations in AuthService; components read
reactively (sidebar and *appHasPermission re-render on permission change). RxJS
only for HTTP streams + refresh coordination. No NgRx — unwarranted at this
scale.

## RBAC integration
core/constants/rbac.constants.ts mirrors the backend permission catalog — keep
in sync; permission codes are the contract. Three UI authorization layers:
route guards (reach the page), nav filter (see the link), *appHasPermission
(see the button).

## Run
    npm install
    npm start            # ng serve
    npm run build        # production build
Point src/environments/environment.ts apiBaseUrl at the FastAPI backend
(default http://localhost:8000/api/v1).

## Notes
- @angular/animations pinned to the exact Angular patch (peer-dep of
  provideAnimationsAsync).
- Tokens in localStorage for the foundation; for higher security migrate
  refresh tokens to httpOnly cookies on the API side — only
  TokenStorageService changes.
