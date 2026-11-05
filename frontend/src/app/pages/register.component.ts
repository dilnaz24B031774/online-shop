import { Component, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { AuthAsideComponent } from '../shared/auth-aside.component';

@Component({
  selector: 'app-register',
  imports: [FormsModule, RouterLink, AuthAsideComponent],
  template: `
    <div class="container page">
      <div class="auth panel">
        <div class="side"><app-auth-aside /></div>
        <form (ngSubmit)="submit()" class="form">
          <h1>{{ i.t('auth.register') }}</h1>
          <p class="muted">{{ i.t('auth.registerText') }}</p>

          @if (errors().length) {
            <div class="alert alert-error">
              @for (e of errors(); track e) { <div>{{ e }}</div> }
            </div>
          }

          <div class="two">
            <div class="field">
              <label for="n">{{ i.t('auth.name') }}</label>
              <input id="n" name="first_name" [(ngModel)]="form.first_name" autocomplete="given-name" />
            </div>
            <div class="field">
              <label for="u">{{ i.t('auth.username') }}</label>
              <input id="u" name="username" [(ngModel)]="form.username" autocomplete="username" required />
            </div>
          </div>
          <div class="field">
            <label for="e">{{ i.t('auth.email') }}</label>
            <input id="e" name="email" type="email" [(ngModel)]="form.email" autocomplete="email" required />
          </div>
          <div class="field">
            <label for="p">{{ i.t('auth.password') }}</label>
            <input id="p" name="password" type="password" [(ngModel)]="form.password" autocomplete="new-password" required />
            <small class="hint">{{ i.t('auth.rules') }}</small>
          </div>
          <button class="btn btn-primary btn-block" type="submit"
                  [disabled]="busy() || !form.username || !form.email || !form.password">{{ i.t('auth.register') }}</button>
          <p class="switch">{{ i.t('auth.haveAccount') }} <a routerLink="/login" [queryParams]="{ returnUrl: returnUrl() }">{{ i.t('auth.login') }}</a></p>
        </form>
      </div>
    </div>
  `,
  styles: [`
    .auth { display: grid; grid-template-columns: 1fr 1.25fr; padding: 0; overflow: hidden; max-width: 960px; margin: 0 auto; }
    .side { position: relative; min-height: 320px; }
    .side app-auth-aside { position: absolute; inset: 0; }
    .form { padding: 2.4rem; }
    h1 { font-size: 2rem; }
    .two { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; }
    .hint { display: block; margin-top: .35rem; color: var(--ink-soft); }
    .switch { margin-top: 1.2rem; }
    @media (max-width: 720px) { .auth { grid-template-columns: 1fr; } .side { height: 140px; } .two { grid-template-columns: 1fr; } }
  `],
})
export class RegisterComponent {
  readonly i = inject(I18nService);
  private auth = inject(AuthService);
  private router = inject(Router);

  readonly returnUrl = input<string>('/');
  form = { first_name: '', username: '', email: '', password: '' };
  readonly busy = signal(false);
  readonly errors = signal<string[]>([]);

  submit() {
    this.busy.set(true);
    this.errors.set([]);
    this.auth.register(this.form).subscribe({
      next: () => this.router.navigateByUrl(this.returnUrl() || '/'),
      error: e => {
        this.busy.set(false);
        // the backend returns {field: [messages]}, e.g. password rules
        const body = e.error && typeof e.error === 'object' ? e.error : null;
        const msgs = body ? Object.values(body).flat().map(String) : [this.i.t('common.error')];
        this.errors.set(msgs.length ? msgs : [this.i.t('common.error')]);
      },
    });
  }
}
