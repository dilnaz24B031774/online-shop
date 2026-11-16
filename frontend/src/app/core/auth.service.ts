import { Injectable, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { Observable, tap, switchMap, map, finalize } from 'rxjs';

import { ApiService, LoginProof } from './api.service';
import { User } from './models';
import { CurrencyService } from './currency.service';

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
  private money = inject(CurrencyService);

  readonly token = signal<string | null>(read(ACCESS));
  readonly user = signal<User | null>(null);
  readonly isLoggedIn = computed(() => !!this.token());
  readonly profileLoading = signal(false);
  readonly profileError = signal(false);
  readonly passwordChanging = signal(false);

  /** Called once when the app starts (see app.config.ts): restores the login after a page reload. */
  restore() {
    if (this.token()) {
      this.refreshProfile().subscribe({
        error: e => { if (e.status === 401) this.logout(false); },
      });
    }
  }

  login(username: string, password: string, proof: LoginProof = {}): Observable<User> {
    return this.api.login(username, password, proof).pipe(
      tap(t => this.saveTokens(t.access, t.refresh)),
      switchMap(() => this.api.me()),
      tap(u => this.setUser(u)),
    );
  }

  register(data: { username: string; email: string; password: string; first_name?: string }): Observable<User> {
    return this.api.register(data).pipe(
      tap(r => { this.saveTokens(r.access, r.refresh); this.setUser(r.user); }),
      map(r => r.user),
    );
  }

  refreshProfile(): Observable<User> {
    this.profileLoading.set(true);
    this.profileError.set(false);
    return this.api.me().pipe(
      tap({ next: u => this.setUser(u), error: () => this.profileError.set(true) }),
      finalize(() => this.profileLoading.set(false)),
    );
  }

  updateProfile(data: Partial<Pick<User, 'username' | 'first_name' | 'last_name' | 'phone' | 'preferred_currency'>>): Observable<User> {
    return this.api.updateMe(data).pipe(tap(u => this.setUser(u)));
  }

  changePassword(data: { current_password: string; new_password: string; new_password_confirm: string }) {
    this.passwordChanging.set(true);
    return this.api.changePassword(data).pipe(
      tap(tokens => this.saveTokens(tokens.access, tokens.refresh)),
      finalize(() => this.passwordChanging.set(false)),
    );
  }

  private setUser(user: User) {
    this.user.set(user);
    this.money.use(user.preferred_currency ?? 'USD');
  }

  logout(goHome = true) {
    this.saveTokens(null, null);
    this.user.set(null);
    this.money.use('USD');
    if (goHome) this.router.navigateByUrl('/');
  }

  private saveTokens(access: string | null, refresh: string | null) {
    write(ACCESS, access);
    write(REFRESH, refresh);
    this.token.set(access);
  }
}
