import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap, switchMap, map } from 'rxjs';

import { ApiService } from './api.service';
import { User } from './models';

const ACCESS = 'sauda.access';
const REFRESH = 'sauda.refresh';

function read(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function write(key: string, value: string | null) {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value); } catch { /* private mode */ }
}

/**
 * Login with JWT tokens.
 * The backend returns an "access" token; every private request sends it
 * in the header  Authorization: Bearer <token>  (see auth.interceptor.ts).
 */
@Injectable({ providedIn: 'root' })
export class AuthService {
  private api = inject(ApiService);
  private router = inject(Router);

  readonly token = signal<string | null>(read(ACCESS));
  readonly user = signal<User | null>(null);
  readonly isLoggedIn = computed(() => !!this.token());

  /** Called once when the app starts (see app.config.ts): restores the login after a page reload. */
  restore() {
    if (this.token()) {
      this.api.me().subscribe({
        next: u => this.user.set(u),
        error: e => { if (e.status === 401) this.logout(false); },
      });
    }
  }

  login(username: string, password: string): Observable<User> {
    return this.api.login(username, password).pipe(
      tap(t => this.saveTokens(t.access, t.refresh)),
      switchMap(() => this.api.me()),
      tap(u => this.user.set(u)),
    );
  }

  register(data: { username: string; email: string; password: string; first_name?: string }): Observable<User> {
    return this.api.register(data).pipe(
      tap(r => { this.saveTokens(r.access, r.refresh); this.user.set(r.user); }),
      map(r => r.user),
    );
  }

  logout(goHome = true) {
    this.saveTokens(null, null);
    this.user.set(null);
    if (goHome) this.router.navigateByUrl('/');
  }

  private saveTokens(access: string | null, refresh: string | null) {
    write(ACCESS, access);
    write(REFRESH, refresh);
    this.token.set(access);
  }
}
