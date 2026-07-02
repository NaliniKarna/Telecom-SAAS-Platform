import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';

import { ApiErrorResponse } from '../models/auth.models';
import { NotificationService } from '../services/notification.service';

/**
 * Translates the API error envelope into user-facing notifications and a
 * clean, typed error for downstream handling. 401s are left to the refresh
 * interceptor; everything else gets a toast unless silenced via header.
 */
export const errorInterceptor: HttpInterceptorFn = (req, next) => {
  const notify = inject(NotificationService);
  const silent = req.headers.has('X-Silent-Error');

  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse) {
        const message = extractMessage(error);

        // 401 is handled by the refresh interceptor; don't double-notify.
        if (error.status !== 401 && !silent) {
          notify.error(message);
        }
        return throwError(() => ({ status: error.status, message }));
      }
      if (!silent) notify.error('An unexpected error occurred.');
      return throwError(() => error);
    }),
  );
};

function extractMessage(error: HttpErrorResponse): string {
  const body = error.error as ApiErrorResponse | undefined;
  if (body?.errors?.length) {
    return body.errors[0].message;
  }
  if (error.status === 0) {
    return 'Cannot reach the server. Check your connection.';
  }
  if (error.status === 403) {
    return 'You do not have permission to do that.';
  }
  return 'Something went wrong. Please try again.';
}
