import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule, NgForm } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { AuthAsideComponent } from '../shared/auth-aside.component';

@Component({
  selector: 'app-forgot-password',
  imports: [FormsModule, RouterLink, AuthAsideComponent],
  template: `
    <div class="container page">
      <div class="auth panel">
        <div class="side"><app-auth-aside /></div>
        <div class="form">
          @if (sent()) {
            <section class="result" role="status">
              <span class="result-icon" aria-hidden="true">✓</span>
              <h1>{{ i.t('reset.checkEmail') }}</h1>
              <p>{{ i.t('reset.emailSent') }}</p>
              <p class="muted">{{ i.t('reset.checkSpam') }}</p>
              <button class="text-button" type="button" (click)="sent.set(false)">{{ i.t('reset.sendAgain') }}</button>
            </section>
          } @else {
            <h1>{{ i.t('reset.title') }}</h1>
            <p class="muted intro">{{ i.t('reset.intro') }}</p>
            <form #form="ngForm" (ngSubmit)="submit(form)" [attr.aria-busy]="busy()">
              @if (errorKey()) { <div class="alert alert-error" role="alert">{{ i.t(errorKey()) }}</div> }
              <fieldset [disabled]="busy()">
                <div class="field">
                  <label for="reset-email">{{ i.t('auth.email') }}</label>
                  <input id="reset-email" name="email" type="email" [(ngModel)]="email" (ngModelChange)="emailError.set(false)"
                         autocomplete="email" autocapitalize="none" spellcheck="false" required email maxlength="254"
                         [attr.aria-invalid]="emailError()" aria-describedby="reset-email-error" />
                  @if (emailError()) { <small id="reset-email-error" class="field-error" role="alert">{{ i.t('reset.emailInvalid') }}</small> }
                </div>
                <button class="btn btn-primary btn-block" type="submit">{{ i.t(busy() ? 'common.loading' : 'reset.sendLink') }}</button>
              </fieldset>
            </form>
          }
          <a class="back" routerLink="/login" [queryParams]="{ returnUrl: safeReturnUrl() }">{{ i.t('reset.backToLogin') }}</a>
        </div>
      </div>
    </div>
  `,
  styleUrl: './password-reset.scss',
})
export class ForgotPasswordComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private destroyRef = inject(DestroyRef);
  readonly returnUrl = input<string>('/');
  email = '';
  readonly busy = signal(false);
  readonly sent = signal(false);
  readonly emailError = signal(false);
  readonly errorKey = signal('');

  safeReturnUrl(): string {
    const value = this.returnUrl() || '/';
    return value.startsWith('/') && !value.startsWith('//') && !value.includes('\\') && !/[\r\n]/.test(value) ? value : '/';
  }

  submit(form: NgForm) {
    if (this.busy()) return;
    this.email = this.email.trim();
    this.emailError.set(!this.email || form.invalid === true);
    this.errorKey.set('');
    if (this.emailError()) return;
    this.busy.set(true);
    this.api.requestPasswordReset(this.email).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.busy.set(false)),
    ).subscribe({
      next: () => this.sent.set(true),
      error: (error: HttpErrorResponse) => {
        if (error.status === 400 && error.error?.email) this.emailError.set(true);
        else this.errorKey.set(error.status === 429 ? 'reset.rateLimited' : 'reset.requestError');
      },
    });
  }
}
