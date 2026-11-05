import { Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

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
        <form (ngSubmit)="submit()" class="form">
          <h1>{{ i.t('auth.login') }}</h1>
          <p class="muted">{{ i.t('auth.loginText') }}</p>

          @if (error()) { <div class="alert alert-error">{{ error() }}</div> }

          <div class="field">
            <label for="u">{{ i.t('auth.username') }}</label>
            <input id="u" name="username" [(ngModel)]="username" autocomplete="username" required />
          </div>
          <div class="field">
            <label for="p">{{ i.t('auth.password') }}</label>
            <input id="p" name="password" type="password" [(ngModel)]="password" autocomplete="current-password" required />
          </div>
          <button class="btn btn-primary btn-block" type="submit" [disabled]="busy() || !username || !password">{{ i.t('auth.login') }}</button>

          <p class="switch">{{ i.t('auth.noAccount') }} <a routerLink="/register" [queryParams]="{ returnUrl: returnUrl() }">{{ i.t('auth.register') }}</a></p>
          <p class="demo muted">{{ i.t('auth.demo') }}</p>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .auth { display: grid; grid-template-columns: 1fr 1.1fr; padding: 0; overflow: hidden; max-width: 900px; margin: 0 auto; }
    .side { position: relative; min-height: 320px; }
    .side app-auth-aside { position: absolute; inset: 0; }
    .form { padding: 2.4rem; }
    h1 { font-size: 2rem; }
    .switch { margin-top: 1.2rem; }
    .demo { font-size: .88rem; background: var(--sky); padding: .6em .9em; border-radius: var(--r-sm); }
    @media (max-width: 720px) { .auth { grid-template-columns: 1fr; } .side { height: 140px; } }
  `],
})
export class LoginComponent {
  readonly i = inject(I18nService);
  private auth = inject(AuthService);
  private router = inject(Router);

  readonly returnUrl = input<string>('/');
  username = '';
  password = '';
  readonly busy = signal(false);
  readonly error = signal('');

  submit() {
    this.busy.set(true);
    this.error.set('');
    this.auth.login(this.username.trim(), this.password).subscribe({
      next: () => this.router.navigateByUrl(this.returnUrl() || '/'),
      error: e => {
        this.busy.set(false);
        this.error.set(e.status === 401 ? this.i.t('auth.wrong') : this.i.t('common.error'));
      },
    });
  }
}
