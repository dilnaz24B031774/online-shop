import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize, Subscription, timer } from 'rxjs';

import { ApiService, TelegramResetChallenge } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { AuthAsideComponent } from '../shared/auth-aside.component';

type Errors = Record<string, string>;

@Component({
  selector: 'app-forgot-password',
  imports: [FormsModule, RouterLink, AuthAsideComponent],
  templateUrl: './forgot-password.component.html',
  styleUrl: './password-reset.scss',
  styles: [`
    .method-switch { display: flex; gap: .4rem; padding: .3rem; border-radius: 12px; background: var(--soft); margin-bottom: 1.4rem; }
    .method-switch button { flex: 1; border: 0; border-radius: 9px; background: transparent; color: var(--ink-soft); padding: .65rem; font: 600 .85rem var(--font-body); cursor: pointer; }
    .method-switch button.active { background: white; color: var(--green-700); box-shadow: 0 1px 5px #173c2912; }
    .method-switch button:focus-visible { outline: 2px solid var(--green-700); }
    .channel-note { border-left: 3px solid var(--amber); padding: .65rem .9rem; background: var(--amber-50); font-size: .8rem; line-height: 1.6; margin-bottom: 1.4rem; }
    .code-input { font-size: 1.4rem; letter-spacing: .35em; font-variant-numeric: tabular-nums; }
  `],
})
export class ForgotPasswordComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private destroyRef = inject(DestroyRef);
  readonly returnUrl = input<string>('/');
  readonly method = signal<'telegram' | 'email'>('telegram');
  readonly busy = signal(false);
  readonly done = signal(false);
  readonly sent = signal(false);
  readonly emailError = signal(false);
  readonly errorKey = signal('');
  readonly errors = signal<Errors>({});
  readonly challenge = signal<TelegramResetChallenge | null>(null);
  readonly remainingSeconds = signal(0);
  readonly showPasswords = signal(false);
  email = '';
  identifier = '';
  code = '';
  password = '';
  confirmation = '';
  private countdown?: Subscription;

  safeReturnUrl(): string {
    const value = this.returnUrl() || '/';
    return value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') && !/[\r\n]/.test(value) ? value : '/';
  }

  chooseMethod(method: 'telegram' | 'email') {
    if (this.busy() || this.method() === method) return;
    this.method.set(method);
    this.errorKey.set('');
    this.emailError.set(false);
    this.sent.set(false);
    this.newTelegramCode();
  }

  edited(field: string) {
    const errors = { ...this.errors() };
    delete errors[field];
    delete errors['form'];
    this.errors.set(errors);
    this.errorKey.set('');
  }

  remainingMinutes(): number { return Math.ceil(this.remainingSeconds() / 60); }

  newTelegramCode() {
    if (this.busy()) return;
    this.countdown?.unsubscribe();
    this.challenge.set(null);
    this.code = '';
    this.password = '';
    this.confirmation = '';
    this.showPasswords.set(false);
    this.errors.set({});
    this.errorKey.set('');
  }

  requestTelegram() {
    if (this.busy()) return;
    this.identifier = this.identifier.trim();
    this.errors.set({});
    this.errorKey.set('');
    if (!this.identifier) { this.errors.set({ identifier: this.i.t('telegram.identifierRequired') }); return; }
    this.busy.set(true);
    this.api.requestTelegramPasswordReset(this.identifier).pipe(
      takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false)),
    ).subscribe({
      next: challenge => {
        this.challenge.set(challenge);
        this.remainingSeconds.set(challenge.expires_in);
        const expiresAt = Date.now() + challenge.expires_in * 1000;
        this.countdown?.unsubscribe();
        this.countdown = timer(0, 1000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
          this.remainingSeconds.set(Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)));
          if (this.remainingSeconds() === 0) this.countdown?.unsubscribe();
        });
      },
      error: (error: HttpErrorResponse) => {
        if (error.status === 400 && error.error?.identifier) this.errors.set({ identifier: this.i.t('telegram.identifierRequired') });
        else this.errorKey.set(this.telegramError(error));
      },
    });
  }

  confirmTelegram() {
    const challenge = this.challenge();
    if (this.busy() || !challenge || this.remainingSeconds() <= 0) return;
    const errors: Errors = {};
    if (!/^[0-9]{6}$/.test(this.code.trim())) errors['code'] = this.i.t('telegram.codeRequired');
    if (!this.password) errors['new_password'] = this.i.t('settings.required');
    else if (this.password.length < 8 || !/\p{Lu}/u.test(this.password) || !/\p{Nd}/u.test(this.password)) errors['new_password'] = this.i.t('auth.rules');
    if (!this.confirmation) errors['new_password_confirm'] = this.i.t('settings.required');
    else if (this.password !== this.confirmation) errors['new_password_confirm'] = this.i.t('settings.passwordMismatch');
    this.errors.set(errors);
    if (Object.keys(errors).length) return;
    this.busy.set(true);
    this.api.confirmTelegramPasswordReset({
      challenge_id: challenge.challenge_id, code: this.code.trim(), new_password: this.password, new_password_confirm: this.confirmation,
    }).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false))).subscribe({
      next: () => {
        this.code = ''; this.password = ''; this.confirmation = '';
        this.showPasswords.set(false);
        this.challenge.set(null);
        this.countdown?.unsubscribe();
        this.auth.logout(false);
        this.done.set(true);
      },
      error: (error: HttpErrorResponse) => {
        if (error.error?.code === 'invalid_telegram_code' || error.error?.challenge_id || Array.isArray(error.error?.code)) {
          this.errors.set({ code: this.i.t('telegram.invalidCode') }); return;
        }
        const errors: Errors = {};
        if (error.status === 400 && error.error && typeof error.error === 'object') {
          for (const field of ['new_password', 'new_password_confirm']) {
            const raw = error.error[field];
            if (!raw) continue;
            const text = (Array.isArray(raw) ? raw : [raw]).map(String).join(' ').toLowerCase();
            errors[field] = this.i.t(field === 'new_password_confirm' ? 'settings.passwordMismatch'
              : text.includes('similar') ? 'settings.passwordSimilar'
              : text.includes('common') ? 'settings.passwordCommon'
              : text.includes('same') || text.includes('different') ? 'settings.passwordSame' : 'auth.rules');
          }
        }
        this.errors.set(Object.keys(errors).length ? errors : { form: this.i.t(this.telegramError(error)) });
      },
    });
  }

  private telegramError(error: HttpErrorResponse): string {
    if (error.status === 429) return 'reset.rateLimited';
    if (error.error?.code === 'telegram_not_configured') return 'telegram.unavailable';
    return 'telegram.requestError';
  }

  submitEmail(form: NgForm) {
    if (this.busy()) return;
    this.email = this.email.trim();
    this.emailError.set(!this.email || form.invalid === true);
    this.errorKey.set('');
    if (this.emailError()) return;
    this.busy.set(true);
    this.api.requestPasswordReset(this.email).pipe(
      takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false)),
    ).subscribe({
      next: () => this.sent.set(true),
      error: (error: HttpErrorResponse) => {
        this.sent.set(false);
        if (error.status === 400 && error.error?.email) this.emailError.set(true);
        else if (error.status === 503 && error.error?.code === 'email_not_configured') this.errorKey.set('reset.emailUnavailable');
        else if (error.status === 503 && error.error?.code === 'email_delivery_failed') this.errorKey.set('reset.emailDeliveryFailed');
        else this.errorKey.set(error.status === 429 ? 'reset.rateLimited' : 'reset.requestError');
      },
    });
  }
}
