import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { AuthAsideComponent } from '../shared/auth-aside.component';

type Errors = Record<string, string>;

@Component({
  selector: 'app-reset-password',
  imports: [FormsModule, RouterLink, AuthAsideComponent],
  template: `
    <div class="container page">
      <div class="auth panel">
        <div class="side"><app-auth-aside /></div>
        <div class="form">
          @if (done()) {
            <section class="result" role="status">
              <span class="result-icon" aria-hidden="true">✓</span>
              <h1>{{ i.t('reset.doneTitle') }}</h1>
              <p>{{ i.t('reset.doneText') }}</p>
              <a class="btn btn-primary btn-block" routerLink="/login">{{ i.t('auth.login') }}</a>
            </section>
          } @else if (invalidLink() || missingLink()) {
            <section class="result" role="alert">
              <h1>{{ i.t('reset.invalidTitle') }}</h1>
              <p class="muted">{{ i.t('reset.invalidText') }}</p>
              <a class="btn btn-primary btn-block" routerLink="/forgot-password">{{ i.t('reset.requestNew') }}</a>
            </section>
          } @else {
            <h1>{{ i.t('reset.newTitle') }}</h1>
            <p class="muted intro">{{ i.t('reset.newIntro') }}</p>
            <form (ngSubmit)="submit()" [attr.aria-busy]="busy()">
              @if (errors()['form']) { <div class="alert alert-error" role="alert">{{ errors()['form'] }}</div> }
              <fieldset [disabled]="busy()">
                <div class="field">
                  <label for="reset-new-password">{{ i.t('settings.newPassword') }}</label>
                  <input id="reset-new-password" name="new_password" [type]="showPasswords() ? 'text' : 'password'"
                         [(ngModel)]="password" (ngModelChange)="edited('new_password')" autocomplete="new-password"
                         required minlength="8" maxlength="4096" [attr.aria-invalid]="!!errors()['new_password']"
                         aria-describedby="reset-password-rules reset-password-error" />
                  @if (errors()['new_password']) { <small id="reset-password-error" class="field-error" role="alert">{{ errors()['new_password'] }}</small> }
                  <small id="reset-password-rules" class="hint">{{ i.t('auth.rules') }}</small>
                </div>
                <div class="field">
                  <label for="reset-confirm-password">{{ i.t('settings.confirmPassword') }}</label>
                  <input id="reset-confirm-password" name="new_password_confirm" [type]="showPasswords() ? 'text' : 'password'"
                         [(ngModel)]="confirmation" (ngModelChange)="edited('new_password_confirm')" autocomplete="new-password"
                         required maxlength="4096" [attr.aria-invalid]="!!errors()['new_password_confirm']" aria-describedby="reset-confirm-error" />
                  @if (errors()['new_password_confirm']) { <small id="reset-confirm-error" class="field-error" role="alert">{{ errors()['new_password_confirm'] }}</small> }
                </div>
                <button class="show-password" type="button" (click)="showPasswords.set(!showPasswords())" [attr.aria-pressed]="showPasswords()">
                  {{ i.t(showPasswords() ? 'auth.hidePassword' : 'auth.showPassword') }}
                </button>
                <button class="btn btn-primary btn-block" type="submit">{{ i.t(busy() ? 'common.loading' : 'reset.savePassword') }}</button>
              </fieldset>
            </form>
          }
          @if (!done()) { <a class="back" routerLink="/login">{{ i.t('reset.backToLogin') }}</a> }
        </div>
      </div>
    </div>
  `,
  styleUrl: './password-reset.scss',
})
export class ResetPasswordComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private destroyRef = inject(DestroyRef);
  readonly uid = input<string>('');
  readonly token = input<string>('');
  readonly missingLink = computed(() => !this.uid() || !this.token());
  readonly invalidLink = signal(false);
  readonly busy = signal(false);
  readonly done = signal(false);
  readonly showPasswords = signal(false);
  readonly errors = signal<Errors>({});
  password = '';
  confirmation = '';

  edited(field: string) {
    const errors = { ...this.errors() };
    delete errors[field];
    delete errors['form'];
    this.errors.set(errors);
  }

  submit() {
    if (this.busy() || this.done() || this.missingLink() || this.invalidLink()) return;
    const errors: Errors = {};
    if (!this.password) errors['new_password'] = this.i.t('settings.required');
    else if (this.password.length < 8 || !/\p{Lu}/u.test(this.password) || !/\p{Nd}/u.test(this.password)) errors['new_password'] = this.i.t('auth.rules');
    if (!this.confirmation) errors['new_password_confirm'] = this.i.t('settings.required');
    else if (this.password !== this.confirmation) errors['new_password_confirm'] = this.i.t('settings.passwordMismatch');
    this.errors.set(errors);
    if (Object.keys(errors).length) return;
    this.busy.set(true);
    this.api.confirmPasswordReset({ uid: this.uid(), token: this.token(), new_password: this.password, new_password_confirm: this.confirmation }).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.busy.set(false)),
    ).subscribe({
      next: () => {
        this.password = '';
        this.confirmation = '';
        this.showPasswords.set(false);
        this.auth.logout(false);
        this.done.set(true);
      },
      error: (error: HttpErrorResponse) => {
        if (error.error?.code === 'invalid_reset_link' || error.error?.uid || error.error?.token) {
          this.invalidLink.set(true);
          return;
        }
        if (error.status === 429) { this.errors.set({ form: this.i.t('reset.rateLimited') }); return; }
        const body: unknown = error.error;
        const errors: Errors = {};
        if (error.status === 400 && body && typeof body === 'object' && !Array.isArray(body)) {
          for (const [field, raw] of Object.entries(body)) {
            if (field !== 'new_password' && field !== 'new_password_confirm') continue;
            const text = (Array.isArray(raw) ? raw : [raw]).map(String).join(' ').toLowerCase();
            errors[field] = this.i.t(field === 'new_password_confirm' ? 'settings.passwordMismatch'
              : text.includes('similar') ? 'settings.passwordSimilar'
              : text.includes('common') ? 'settings.passwordCommon'
              : text.includes('different') || text.includes('same') ? 'settings.passwordSame' : 'auth.rules');
          }
        }
        this.errors.set(Object.keys(errors).length ? errors : { form: this.i.t('reset.saveError') });
      },
    });
  }
}
