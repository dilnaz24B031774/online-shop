import { DatePipe } from '@angular/common';
import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, effect, inject, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { finalize, Subscription, timer } from 'rxjs';

import { ApiService, TelegramStatus } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';

@Component({
  selector: 'app-telegram-link',
  imports: [FormsModule, DatePipe],
  template: `
    <section class="panel telegram-card" aria-labelledby="telegram-title">
      <div class="heading">
        <span class="icon" aria-hidden="true"><svg viewBox="0 0 24 24"><path d="m21 4-4 17-6-5-3 3v-6L3 11zM8 13 21 4M11 16l10-12"/></svg></span>
        <div><h2 id="telegram-title">{{ i.t('telegram.settingsTitle') }}</h2><p>{{ i.t('telegram.settingsHint') }}</p></div>
      </div>
      @if (errorKey()) { <div class="alert alert-error" role="alert">{{ i.t(errorKey()) }}</div> }
      @if (noticeKey()) { <p class="notice" role="status">{{ i.t(noticeKey()) }}</p> }
      @if (!status() && loading()) {
        <p class="muted" role="status">{{ i.t('common.loading') }}</p>
      } @else if (!status()) {
        <button class="btn btn-outline" type="button" [disabled]="loading()" (click)="checkStatus()">{{ i.t('settings.retry') }}</button>
      } @else if (status()?.linked) {
        <div class="connection" role="status">
          <span class="connected-mark" aria-hidden="true">✓</span>
          <div><strong>{{ status()?.username ? '@' + status()?.username : i.t('telegram.connected') }}</strong>
          @if (status()?.linked_at) { <small>{{ i.t('telegram.linkedSince') }} {{ status()?.linked_at | date: 'mediumDate' }}</small> }</div>
        </div>
        <p class="hint">{{ i.t('telegram.unlinkHint') }}</p>
        <form (ngSubmit)="unlink()" novalidate [attr.aria-busy]="busy()">
          <fieldset [disabled]="busy() || loading()">
            <div class="field">
              <label for="telegram-unlink-password">{{ i.t('settings.currentPassword') }}</label>
              <input id="telegram-unlink-password" name="current_password" type="password" [(ngModel)]="password" (ngModelChange)="clearErrors()"
                     autocomplete="current-password" required maxlength="4096" [attr.aria-invalid]="!!passwordError()" aria-describedby="telegram-password-error" />
              @if (passwordError()) { <small id="telegram-password-error" class="field-error" role="alert">{{ i.t(passwordError()) }}</small> }
            </div>
            <button class="btn btn-outline" type="submit">{{ i.t(busy() ? 'common.loading' : 'telegram.unlink') }}</button>
          </fieldset>
        </form>
      } @else if (!status()?.configured) {
        <p class="muted" role="status">{{ i.t('telegram.unavailable') }}</p>
        <button class="btn btn-outline" type="button" [disabled]="loading()" (click)="checkStatus()">{{ i.t('settings.retry') }}</button>
      } @else if (linkUrl()) {
        <p class="pending-hint">{{ i.t('telegram.finishLink') }}</p>
        @if (remainingSeconds() > 0) {
          <a class="btn btn-primary" [href]="linkUrl()" target="_blank" rel="noopener noreferrer">{{ i.t('telegram.openBot') }} <span aria-hidden="true">↗</span></a>
          <p class="hint">{{ i.t('telegram.linkExpires', { n: remainingMinutes() }) }}</p>
          <div class="pending-actions">
            <button class="btn btn-outline" type="button" [disabled]="loading()" (click)="checkStatus()">{{ i.t(loading() ? 'common.loading' : 'telegram.checkConnection') }}</button>
            <button class="text-button" type="button" [disabled]="loading()" (click)="newLink()">{{ i.t('telegram.newLink') }}</button>
          </div>
        } @else {
          <p class="muted" role="status">{{ i.t('telegram.linkExpired') }}</p>
          <button class="btn btn-primary" type="button" (click)="newLink()">{{ i.t('telegram.newLink') }}</button>
        }
      } @else {
        <p class="hint">{{ i.t('telegram.passwordToLink') }}</p>
        <form (ngSubmit)="link()" novalidate [attr.aria-busy]="busy()">
          <fieldset [disabled]="busy() || loading()">
            <div class="field">
              <label for="telegram-link-password">{{ i.t('settings.currentPassword') }}</label>
              <input id="telegram-link-password" name="current_password" type="password" [(ngModel)]="password" (ngModelChange)="clearErrors()"
                     autocomplete="current-password" required maxlength="4096" [attr.aria-invalid]="!!passwordError()" aria-describedby="telegram-password-error" />
              @if (passwordError()) { <small id="telegram-password-error" class="field-error" role="alert">{{ i.t(passwordError()) }}</small> }
            </div>
            <button class="btn btn-primary" type="submit">{{ i.t(busy() ? 'common.loading' : 'telegram.connect') }}</button>
          </fieldset>
        </form>
      }
    </section>
  `,
  styles: [`
    :host { display: block; }
    .telegram-card { padding: 1.65rem 1.8rem; box-shadow: 0 3px 14px -10px #0e3b2e20; }
    .heading { display: flex; align-items: flex-start; gap: .85rem; margin-bottom: 1.25rem; }
    .heading h2 { font-size: 1.15rem; margin: .1rem 0 .3rem; }
    .heading p { color: var(--muted); font-size: .82rem; margin: 0; }
    .icon { display: grid; place-items: center; flex-shrink: 0; width: 40px; height: 40px; border-radius: 12px; background: var(--green-50); color: var(--green-700); }
    .icon svg { width: 21px; height: 21px; fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linejoin: round; }
    .hint { color: var(--muted); font-size: .78rem; line-height: 1.6; }
    .connection { display: flex; align-items: center; gap: .75rem; padding: .85rem 1rem; border-radius: 12px; background: var(--green-50); margin-bottom: 1rem; }
    .connected-mark { color: var(--green-700); font-size: 1.2rem; }
    .connection strong { color: var(--green-700); overflow-wrap: anywhere; }
    .connection small { display: block; margin-top: .2rem; color: var(--muted); font-size: .75rem; }
    fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
    label { font-size: .82rem; }
    input { min-height: 45px; font-size: .9rem; }
    .field { max-width: 380px; }
    .field-error { display: block; color: #a8322a; font-size: .77rem; margin-top: .35rem; }
    input[aria-invalid="true"] { border-color: #a8322a; }
    .btn { font-size: .83rem; padding: .7rem 1.1rem; }
    .notice { color: var(--green-700); font-size: .82rem; }
    .pending-hint { font-size: .85rem; line-height: 1.65; }
    .pending-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 1rem; }
    .text-button { border: 0; padding: .4rem 0; background: transparent; color: var(--green-700); font: inherit; font-size: .8rem; text-decoration: underline; cursor: pointer; }
    @media (max-width: 860px) { .telegram-card { padding-inline: 1.25rem; } }
    @media (max-width: 460px) { .telegram-card { padding: 1.25rem 1rem; } }
  `],
})
export class TelegramLinkComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private destroyRef = inject(DestroyRef);
  readonly status = signal<TelegramStatus | null>(null);
  readonly loading = signal(false);
  readonly busy = signal(false);
  readonly errorKey = signal('');
  readonly passwordError = signal('');
  readonly noticeKey = signal('');
  readonly linkUrl = signal<string | null>(null);
  readonly remainingSeconds = signal(0);
  password = '';
  private statusRequest?: Subscription;
  private actionRequest?: Subscription;
  private countdown?: Subscription;

  constructor() {
    effect(onCleanup => {
      const accountId = this.auth.user()?.id;
      untracked(() => {
        this.status.set(null);
        this.password = '';
        this.linkUrl.set(null);
        this.clearErrors();
        this.noticeKey.set('');
        if (accountId) this.loadStatus(accountId);
      });
      onCleanup(() => {
        this.statusRequest?.unsubscribe();
        this.actionRequest?.unsubscribe();
        this.countdown?.unsubscribe();
      });
    });
  }

  clearErrors() { this.passwordError.set(''); this.errorKey.set(''); }
  remainingMinutes(): number { return Math.ceil(this.remainingSeconds() / 60); }

  newLink() {
    this.linkUrl.set(null);
    this.countdown?.unsubscribe();
    this.password = '';
    this.clearErrors();
    this.noticeKey.set('');
  }

  checkStatus() {
    const accountId = this.auth.user()?.id;
    if (accountId && !this.loading() && !this.busy()) this.loadStatus(accountId);
  }

  private loadStatus(accountId: number) {
    this.statusRequest?.unsubscribe();
    this.loading.set(true);
    this.errorKey.set('');
    this.statusRequest = this.api.telegramStatus().pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.loading.set(false)),
    ).subscribe({
      next: status => {
        if (this.auth.user()?.id !== accountId) return;
        this.status.set(status);
        if (status.linked && this.linkUrl()) {
          this.linkUrl.set(null);
          this.countdown?.unsubscribe();
          this.noticeKey.set('telegram.linkedNotice');
        } else if (this.linkUrl()) this.noticeKey.set('telegram.stillPending');
      },
      error: () => { if (this.auth.user()?.id === accountId) this.errorKey.set('telegram.loadError'); },
    });
  }

  link() {
    const accountId = this.auth.user()?.id;
    if (!accountId || this.busy() || this.loading() || !this.passwordValid()) return;
    const password = this.password;
    this.password = '';
    this.busy.set(true);
    this.noticeKey.set('');
    this.actionRequest = this.api.linkTelegram(password).pipe(
      takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false)),
    ).subscribe({
      next: result => {
        if (this.auth.user()?.id !== accountId) return;
        if (!/^https:\/\/t\.me\/[A-Za-z0-9_]+\?start=[A-Za-z0-9_-]+$/.test(result.link_url)) {
          this.errorKey.set('telegram.requestError'); return;
        }
        this.linkUrl.set(result.link_url);
        this.remainingSeconds.set(result.expires_in);
        const expiresAt = Date.now() + result.expires_in * 1000;
        this.countdown?.unsubscribe();
        this.countdown = timer(0, 1000).pipe(takeUntilDestroyed(this.destroyRef)).subscribe(() => {
          this.remainingSeconds.set(Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000)));
          if (this.remainingSeconds() === 0) this.countdown?.unsubscribe();
        });
      },
      error: (error: HttpErrorResponse) => { if (this.auth.user()?.id === accountId) this.actionError(error); },
    });
  }

  unlink() {
    const accountId = this.auth.user()?.id;
    if (!accountId || this.busy() || this.loading() || !this.passwordValid()) return;
    const password = this.password;
    this.password = '';
    this.busy.set(true);
    this.noticeKey.set('');
    this.actionRequest = this.api.unlinkTelegram(password).pipe(
      takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false)),
    ).subscribe({
      next: () => {
        if (this.auth.user()?.id !== accountId) return;
        this.status.update(status => status ? { ...status, linked: false, username: null, linked_at: null } : status);
        this.linkUrl.set(null);
        this.countdown?.unsubscribe();
        this.noticeKey.set('telegram.unlinkedNotice');
      },
      error: (error: HttpErrorResponse) => { if (this.auth.user()?.id === accountId) this.actionError(error); },
    });
  }

  private passwordValid(): boolean {
    this.clearErrors();
    if (!this.password) { this.passwordError.set('settings.required'); return false; }
    return true;
  }

  private actionError(error: HttpErrorResponse) {
    if (error.error?.current_password) this.passwordError.set('settings.currentPasswordWrong');
    else if (error.status === 429) this.errorKey.set('reset.rateLimited');
    else if (error.error?.code === 'telegram_not_configured') this.errorKey.set('telegram.unavailable');
    else if (error.error?.code === 'telegram_already_linked') {
      this.errorKey.set('telegram.alreadyLinked');
      const accountId = this.auth.user()?.id;
      if (accountId) this.loadStatus(accountId);
    } else this.errorKey.set('telegram.requestError');
  }
}
