import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { Subscription } from 'rxjs';

import { ApiService, LoginChallenge, LoginFailure } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { AuthAsideComponent } from '../shared/auth-aside.component';

@Component({
  selector: 'app-login',
  imports: [FormsModule, RouterLink, AuthAsideComponent],
  template: `
    <div class="container page">
      <div class="auth panel">
        <div class="side"><app-auth-aside /></div>
        <form (ngSubmit)="submit()" class="form" [attr.aria-busy]="busy() || challengeLoading()">
          <h1>{{ i.t('auth.login') }}</h1>
          <p class="muted">{{ i.t('auth.loginText') }}</p>

          @if (errorKey()) {
            <div class="alert alert-error" role="alert">{{ i.t(errorKey()) }}</div>
          }
          @if (cooldownSeconds() > 0) {
            <div class="cooldown" role="status">
              <strong>{{ i.t('auth.lockedTitle') }}</strong>
              <p>{{ i.t('auth.waitBeforeRetry') }} <span class="clock" aria-live="off">{{ cooldownText() }}</span></p>
            </div>
          } @else if (remainingAttempts() !== null) {
            <p class="attempts" role="status">{{ i.t('auth.attemptsLeft', { n: remainingAttempts()! }) }}</p>
          }

          <div class="field">
            <label for="u">{{ i.t('auth.username') }}</label>
            <input id="u" name="username" [(ngModel)]="username" autocomplete="username" autocapitalize="none" spellcheck="false" required />
          </div>
          <div class="field">
            <label for="p">{{ i.t('auth.password') }}</label>
            <div class="password-field">
              <input id="p" name="password" [type]="showPassword() ? 'text' : 'password'" [(ngModel)]="password" autocomplete="current-password" required />
              <button class="password-toggle" type="button" (click)="showPassword.set(!showPassword())"
                      [attr.aria-label]="i.t(showPassword() ? 'auth.hidePassword' : 'auth.showPassword')"
                      [attr.aria-pressed]="showPassword()" aria-controls="p">
                {{ i.t(showPassword() ? 'auth.hide' : 'auth.show') }}
              </button>
            </div>
          </div>

          <div class="website-field" aria-hidden="true">
            <label for="login-website">Website</label>
            <input id="login-website" name="website" type="text" [(ngModel)]="website" tabindex="-1" autocomplete="off" />
          </div>

          @if (challengeRequired() && cooldownSeconds() === 0) {
            <fieldset class="challenge">
              <legend>{{ i.t('auth.botCheck') }}</legend>
              <p class="muted">{{ i.t('auth.botCheckHint') }}</p>
              @if (challengeLoading()) {
                <p role="status">{{ i.t('common.loading') }}</p>
              } @else {
                @if (challenge(); as question) {
                <label for="challenge-answer">{{ question.prompt }}</label>
                <input id="challenge-answer" name="challenge_answer" [(ngModel)]="challengeAnswer" inputmode="numeric"
                       autocomplete="off" [placeholder]="i.t('auth.answer')" required aria-describedby="challenge-help" />
                <small id="challenge-help" class="muted">{{ i.t('auth.challengeExpires') }}</small>
                }
              }
              <button class="refresh-challenge" type="button" (click)="loadChallenge()" [disabled]="challengeLoading() || busy()">
                {{ i.t('auth.newChallenge') }}
              </button>
            </fieldset>
          }

          <button class="btn btn-primary btn-block" type="submit"
                  [disabled]="busy() || cooldownSeconds() > 0 || challengeLoading() || !username.trim() || !password || (challengeRequired() && (!challenge() || !challengeAnswer.trim()))">
            {{ i.t(busy() ? 'common.loading' : 'auth.login') }}
          </button>

          <p class="switch">{{ i.t('auth.noAccount') }} <a routerLink="/register" [queryParams]="{ returnUrl: safeReturnUrl() }">{{ i.t('auth.register') }}</a></p>
          <p class="security-note muted">{{ i.t('auth.loginProtection') }}</p>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .auth { display: grid; grid-template-columns: 1fr 1.1fr; padding: 0; overflow: hidden; max-width: 900px; margin: 0 auto; }
    .side { position: relative; min-height: 320px; }
    .side app-auth-aside { position: absolute; inset: 0; }
    .form { padding: 2.4rem; min-width: 0; position: relative; }
    h1 { font-size: 2rem; }
    .switch { margin-top: 1.2rem; }
    .security-note { font-size: .82rem; border-top: 1px solid var(--line); padding-top: 1rem; margin-bottom: 0; }
    .password-field { position: relative; }
    .password-field input { padding-right: 6.7rem; }
    .password-toggle { position: absolute; right: .65rem; top: 50%; transform: translateY(-50%); border: 0; background: transparent; color: var(--green-700); font: inherit; font-size: .78rem; cursor: pointer; padding: .35rem; }
    .password-toggle:focus-visible, .refresh-challenge:focus-visible { outline: 2px solid var(--green-700); outline-offset: 3px; }
    .website-field { position: absolute; width: 1px; height: 1px; overflow: hidden; clip-path: inset(50%); white-space: nowrap; }
    .attempts { color: #8b5e12; font-size: .86rem; }
    .cooldown { border: 1px solid #edd3a3; border-radius: var(--r-sm); background: #fff8e9; padding: .9rem 1rem; margin: 1rem 0; font-size: .9rem; color: #745014; }
    .cooldown p { margin: .35rem 0 0; }
    .clock { font-variant-numeric: tabular-nums; font-weight: 700; }
    .challenge { border: 1px solid var(--line); border-radius: var(--r-sm); padding: .8rem 1rem 1rem; margin: 1.3rem 0; min-width: 0; }
    .challenge legend { padding: 0 .4rem; font-weight: 650; font-size: .9rem; }
    .challenge p { font-size: .82rem; margin: .2rem 0 .7rem; }
    .challenge label { display: block; margin-bottom: .45rem; font-weight: 650; }
    .challenge small { display: block; font-size: .75rem; margin-top: .4rem; }
    .refresh-challenge { display: inline-block; margin-top: .8rem; padding: 0; border: 0; background: none; color: var(--green-700); cursor: pointer; text-decoration: underline; font: inherit; font-size: .8rem; }
    .refresh-challenge:disabled { opacity: .55; cursor: wait; }
    @media (max-width: 720px) { .auth { grid-template-columns: 1fr; } .side { height: 140px; min-height: 140px; } .form { padding: 1.6rem; } }
  `],
})
export class LoginComponent {
  readonly i = inject(I18nService);
  private auth = inject(AuthService);
  private api = inject(ApiService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

  readonly returnUrl = input<string>('/');
  username = '';
  password = '';
  website = '';
  challengeAnswer = '';
  readonly busy = signal(false);
  readonly errorKey = signal('');
  readonly showPassword = signal(false);
  readonly remainingAttempts = signal<number | null>(null);
  readonly challengeRequired = signal(false);
  readonly challenge = signal<LoginChallenge | null>(null);
  readonly challengeLoading = signal(false);
  readonly cooldownSeconds = signal(0);
  private challengeExpiresAt = 0;
  private cooldownTimer: ReturnType<typeof setInterval> | undefined;
  private challengeRequest?: Subscription;

  constructor() {
    this.destroyRef.onDestroy(() => {
      if (this.cooldownTimer) clearInterval(this.cooldownTimer);
      this.challengeRequest?.unsubscribe();
    });
  }

  safeReturnUrl(): string {
    const value = this.returnUrl();
    return value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') && !/[\r\n]/.test(value) ? value : '/';
  }

  cooldownText(): string {
    const seconds = this.cooldownSeconds();
    return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`;
  }

  loadChallenge() {
    if (this.busy() || this.cooldownSeconds() > 0) return;
    this.challengeRequest?.unsubscribe();
    this.challenge.set(null);
    this.challengeAnswer = '';
    this.challengeLoading.set(true);
    this.challengeRequest = this.api.securityChallenge().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: question => {
        this.challenge.set(question);
        this.challengeExpiresAt = Date.now() + question.expires_in * 1000;
        this.challengeLoading.set(false);
      },
      error: (e: HttpErrorResponse) => {
        this.challengeLoading.set(false);
        if (e.status === 429) {
          this.errorKey.set('auth.tooManyRequests');
          this.startCooldown(this.retryAfter(e));
        } else {
          this.errorKey.set('auth.challengeUnavailable');
        }
      },
    });
  }

  submit() {
    if (this.busy() || this.challengeLoading() || this.cooldownSeconds() > 0 || !this.username.trim() || !this.password) return;
    if (this.challengeRequired() && (!this.challenge() || !this.challengeAnswer.trim())) {
      this.errorKey.set('auth.solveChallenge');
      if (!this.challenge()) this.loadChallenge();
      return;
    }
    if (this.challengeRequired() && Date.now() >= this.challengeExpiresAt) {
      this.errorKey.set('auth.challengeExpired');
      this.loadChallenge();
      return;
    }
    this.busy.set(true);
    this.errorKey.set('');
    this.auth.login(this.username.trim(), this.password, {
      website: this.website,
      ...(this.challengeRequired() && this.challenge() ? {
        challenge_id: this.challenge()!.id,
        challenge_answer: this.challengeAnswer.trim(),
      } : {}),
    }).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.password = '';
        this.showPassword.set(false);
        this.router.navigateByUrl(this.safeReturnUrl());
      },
      error: (e: HttpErrorResponse) => {
        this.busy.set(false);
        const body = this.failureBody(e);
        if (typeof body.remaining_attempts === 'number') this.remainingAttempts.set(Math.max(0, Math.floor(body.remaining_attempts)));
        if (e.status === 429) {
          this.errorKey.set('auth.tooManyRequests');
          this.remainingAttempts.set(null);
          this.challenge.set(null);
          this.startCooldown(this.retryAfter(e));
          return;
        }
        this.errorKey.set(body.code === 'challenge_required' ? 'auth.solveChallenge' : e.status === 401 ? 'auth.wrong' : e.status === 400 ? 'auth.loginInvalid' : 'common.error');
        if (body.challenge_required || body.code === 'challenge_required' || this.challengeRequired()) {
          this.challengeRequired.set(true);
          this.loadChallenge();
        }
      },
    });
  }

  private failureBody(e: HttpErrorResponse): LoginFailure {
    return e.error && typeof e.error === 'object' ? e.error as LoginFailure : {};
  }

  private retryAfter(e: HttpErrorResponse): number {
    const value = Number(this.failureBody(e).retry_after ?? e.headers.get('Retry-After') ?? 300);
    return Number.isFinite(value) && value > 0 ? Math.ceil(value) : 300;
  }

  private startCooldown(seconds: number) {
    if (this.cooldownTimer) clearInterval(this.cooldownTimer);
    const deadline = Date.now() + seconds * 1000;
    this.cooldownSeconds.set(seconds);
    this.cooldownTimer = setInterval(() => {
      const left = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      this.cooldownSeconds.set(left);
      if (left === 0) {
        clearInterval(this.cooldownTimer);
        this.cooldownTimer = undefined;
        this.errorKey.set('');
        this.remainingAttempts.set(null);
        if (this.challengeRequired()) this.loadChallenge();
      }
    }, 1000);
  }
}
