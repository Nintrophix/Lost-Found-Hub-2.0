import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { Observable, catchError, firstValueFrom, of, tap, throwError } from 'rxjs';

import { Api, Role, User } from './api';

@Injectable({ providedIn: 'root' })
export class Auth {
  private readonly api = inject(Api);
  readonly user = signal<User | null>(null);
  /** Email domains allowed to sign in, from the backend (e.g. ["srmist.edu.in"]). */
  readonly allowedDomains = signal<string[]>([]);
  readonly domainHint = computed(() => this.allowedDomains().map((d) => '@' + d).join(' or '));
  readonly signedIn = computed(() => this.user() !== null);
  readonly isStaff = computed(() => ['STAFF', 'ADMIN'].includes(this.user()?.role ?? ''));
  readonly isAdmin = computed(() => this.user()?.role === 'ADMIN');

  /** Called once at startup. Never throws: an unreachable API simply means "signed out". */
  load(): Promise<unknown> {
    return firstValueFrom(
      this.api.session().pipe(
        tap(({ user, allowed_email_domains }) => {
          this.user.set(user);
          this.allowedDomains.set(allowed_email_domains);
        }),
        catchError(() => of(null)),
      ),
    );
  }

  login(email: string, password: string): Observable<User> {
    return this.api.login(email, password).pipe(tap((user) => this.user.set(user)));
  }

  logout(): Observable<unknown> {
    return this.api.logout().pipe(
      catchError(() => of(null)),
      tap(() => this.user.set(null)),
    );
  }

  /** Client-side courtesy check; the backend enforces the same rule. */
  emailAllowed(email: string): boolean {
    const domain = email.trim().toLowerCase().split('@').pop() ?? '';
    const allowed = this.allowedDomains();
    return allowed.length === 0 || allowed.includes(domain);
  }

  hasRole(roles: Role[]): boolean {
    const role = this.user()?.role;
    return role !== undefined && roles.includes(role);
  }
}

function toLogin(router: Router, url: string) {
  return router.createUrlTree(['/login'], { queryParams: { returnUrl: url } });
}

export const signedInGuard: CanActivateFn = (_route, state) => {
  return inject(Auth).signedIn() || toLogin(inject(Router), state.url);
};

export function roleGuard(roles: Role[]): CanActivateFn {
  return (_route, state) => {
    const auth = inject(Auth);
    const router = inject(Router);
    if (!auth.signedIn()) return toLogin(router, state.url);
    return auth.hasRole(roles) || router.createUrlTree(['/dashboard']);
  };
}

/** If the session expires mid-visit, clear local state and send the user to sign in again. */
export const sessionExpiryInterceptor: HttpInterceptorFn = (req, next) => {
  const auth = inject(Auth);
  const router = inject(Router);
  return next(req).pipe(
    catchError((error: unknown) => {
      if (error instanceof HttpErrorResponse && error.status === 401 && auth.signedIn() && !req.url.endsWith('/login')) {
        auth.user.set(null);
        router.navigate(['/login'], { queryParams: { returnUrl: router.url } });
      }
      return throwError(() => error);
    }),
  );
};
