import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, throwError } from 'rxjs';

import { API_URL } from './api.service';
import { AuthService } from './auth.service';

/** Adds the JWT token to every request to our backend. */
export const authInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(AuthService);
  const router = inject(Router);
  const token = auth.token();

  const isOurApi = req.url === API_URL || req.url.startsWith(`${API_URL}/`);
  const isPublicAuth = req.url.startsWith(`${API_URL}/auth/`);
  const request = token && isOurApi && !isPublicAuth
    ? req.clone({ setHeaders: { Authorization: `Bearer ${token}` } })
    : req;

  return next(request).pipe(
    catchError((err: HttpErrorResponse) => {
      // token expired or wrong -> log out and ask to sign in again
      // A password change replaces the tokens. Ignore failures from requests
      // that were already in flight with the previous token.
      const passwordRequest = req.url === `${API_URL}/me/password/`;
      if (err.status === 401 && token && auth.token() === token && (!auth.passwordChanging() || passwordRequest) && isOurApi && !isPublicAuth) {
        auth.logout(false);
        router.navigate(['/login'], { queryParams: { returnUrl: router.url } });
      }
      return throwError(() => err);
    }),
  );
};
