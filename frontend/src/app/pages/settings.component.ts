import { Component, computed, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { finalize } from 'rxjs';

import { AuthService } from '../core/auth.service';
import { CURRENCIES, CurrencyCode } from '../core/currency.service';
import { I18nService } from '../core/i18n.service';
import { User } from '../core/models';
import { TelegramLinkComponent } from '../shared/telegram-link.component';

type Errors = Record<string, string>;
type Profile = Pick<User, 'username' | 'first_name' | 'last_name' | 'phone'>;

@Component({
  selector: 'app-settings',
  imports: [FormsModule, RouterLink, TelegramLinkComponent],
  templateUrl: './settings.component.html',
  styleUrl: './settings.component.scss',
})
export class SettingsComponent {
  readonly i = inject(I18nService);
  readonly auth = inject(AuthService);
  readonly currencies = CURRENCIES;
  readonly ready = signal(false);
  readonly initials = computed(() => {
    const u = this.auth.user();
    return `${u?.first_name?.charAt(0) || u?.username?.charAt(0) || '?'}${u?.last_name?.charAt(0) || ''}`.toUpperCase();
  });
  readonly displayName = computed(() => {
    const u = this.auth.user();
    return [u?.first_name, u?.last_name].filter(Boolean).join(' ') || u?.username || '';
  });
  profile: Profile = { username: '', first_name: '', last_name: '', phone: '' };
  currency: CurrencyCode = 'USD';
  password = { current_password: '', new_password: '', new_password_confirm: '' };
  readonly profileBusy = signal(false);
  readonly currencyBusy = signal(false);
  readonly passwordBusy = signal(false);
  readonly saving = computed(() => this.profileBusy() || this.currencyBusy() || this.passwordBusy());
  readonly profileSaved = signal(false);
  readonly currencySaved = signal(false);
  readonly passwordSaved = signal(false);
  readonly showPasswords = signal(false);
  readonly profileErrors = signal<Errors>({});
  readonly currencyErrors = signal<Errors>({});
  readonly passwordErrors = signal<Errors>({});
  private loadedId: number | null = null;

  constructor() {
    // A late /me response fills the form once; changing language or saving preferences
    // must not erase unsaved edits in another form.
    effect(() => {
      const user = this.auth.user();
      if (user && user.id !== this.loadedId) {
        this.loadedId = user.id;
        this.fillProfile(user);
        this.currency = user.preferred_currency || 'USD';
        this.ready.set(true);
      }
    });
  }

  retry() {
    if (!this.auth.profileLoading()) this.auth.refreshProfile().subscribe({ error: () => {} });
  }

  profileEdited(field: string) {
    this.profileSaved.set(false);
    const errors = { ...this.profileErrors() };
    delete errors[field];
    delete errors['form'];
    this.profileErrors.set(errors);
  }

  passwordEdited(field: string) {
    this.passwordSaved.set(false);
    const errors = { ...this.passwordErrors() };
    delete errors[field];
    delete errors['form'];
    this.passwordErrors.set(errors);
  }

  saveProfile() {
    if (this.saving()) return;
    this.profileSaved.set(false);
    const data = {
      username: this.profile.username.trim(),
      first_name: this.profile.first_name.trim(),
      last_name: this.profile.last_name.trim(),
      phone: this.profile.phone.trim(),
    };
    const errors: Errors = {};
    if (!data.username) errors['username'] = this.i.t('settings.required');
    else if (!/^[\p{L}\p{N}\p{M}@.+_\-]+$/u.test(data.username)) errors['username'] = this.i.t('settings.usernameInvalid');
    if (data.phone && (!/^\+?[\d\s()\-]+$/.test(data.phone) || !/^\d{7,15}$/.test(data.phone.replace(/\D/g, '')))) {
      errors['phone'] = this.i.t('settings.phoneInvalid');
    }
    this.profileErrors.set(errors);
    if (Object.keys(errors).length) return;
    this.profileBusy.set(true);
    this.auth.updateProfile(data).pipe(finalize(() => this.profileBusy.set(false))).subscribe({
      next: user => { this.fillProfile(user); this.profileSaved.set(true); },
      error: error => this.profileErrors.set(this.errorsFrom(error)),
    });
  }

  saveCurrency() {
    if (this.saving()) return;
    this.currencySaved.set(false);
    this.currencyErrors.set({});
    this.currencyBusy.set(true);
    this.auth.updateProfile({ preferred_currency: this.currency }).pipe(finalize(() => this.currencyBusy.set(false))).subscribe({
      next: user => { this.currency = user.preferred_currency; this.currencySaved.set(true); },
      error: error => this.currencyErrors.set(this.errorsFrom(error)),
    });
  }

  savePassword() {
    if (this.saving()) return;
    this.passwordSaved.set(false);
    const errors: Errors = {};
    if (!this.password.current_password) errors['current_password'] = this.i.t('settings.required');
    if (!this.password.new_password) errors['new_password'] = this.i.t('settings.required');
    else if (this.password.new_password.length < 8 || !/\p{Lu}/u.test(this.password.new_password) || !/\p{Nd}/u.test(this.password.new_password)) {
      errors['new_password'] = this.i.t('auth.rules');
    } else if (this.password.current_password === this.password.new_password) {
      errors['new_password'] = this.i.t('settings.passwordSame');
    }
    if (!this.password.new_password_confirm) errors['new_password_confirm'] = this.i.t('settings.required');
    else if (this.password.new_password !== this.password.new_password_confirm) errors['new_password_confirm'] = this.i.t('settings.passwordMismatch');
    this.passwordErrors.set(errors);
    if (Object.keys(errors).length) return;
    this.passwordBusy.set(true);
    this.auth.changePassword({ ...this.password }).pipe(finalize(() => this.passwordBusy.set(false))).subscribe({
      next: () => {
        this.password = { current_password: '', new_password: '', new_password_confirm: '' };
        this.showPasswords.set(false);
        this.passwordSaved.set(true);
      },
      error: error => this.passwordErrors.set(this.errorsFrom(error)),
    });
  }

  private fillProfile(user: User) {
    this.profile = { username: user.username, first_name: user.first_name, last_name: user.last_name, phone: user.phone };
  }

  private errorsFrom(error: HttpErrorResponse): Errors {
    if (!error.status || error.status >= 500) return { form: this.i.t('settings.saveError') };
    if (error.status === 401) return { form: this.i.t('settings.sessionExpired') };
    const body: unknown = error.error;
    if (!body || typeof body !== 'object' || Array.isArray(body)) return { form: this.i.t('settings.saveError') };
    const errors: Errors = {};
    for (const [field, value] of Object.entries(body)) {
      const messages = (Array.isArray(value) ? value : [value]).map(String);
      errors[field === 'non_field_errors' || field === 'detail' ? 'form' : field] = messages.map(message => this.translateError(field, message)).join(' ');
    }
    return Object.keys(errors).length ? errors : { form: this.i.t('settings.saveError') };
  }

  private translateError(field: string, text: string): string {
    const value = text.toLowerCase();
    if (value.includes('required') || value.includes('may not be blank')) return this.i.t('settings.required');
    if (field === 'current_password') return this.i.t('settings.currentPasswordWrong');
    if (field === 'phone') return this.i.t('settings.phoneInvalid');
    if (field === 'username') return this.i.t(value.includes('taken') || value.includes('exists') || value.includes('unique') ? 'settings.usernameTaken' : 'settings.usernameInvalid');
    if (field === 'preferred_currency') return this.i.t('settings.currencyInvalid');
    if (field === 'new_password_confirm' || value.includes('match')) return this.i.t('settings.passwordMismatch');
    if (value.includes('same') || value.includes('different')) return this.i.t('settings.passwordSame');
    if (value.includes('similar')) return this.i.t('settings.passwordSimilar');
    if (value.includes('common')) return this.i.t('settings.passwordCommon');
    if (field === 'new_password' || field === 'password') return this.i.t('auth.rules');
    return this.i.t('settings.saveError');
  }
}
