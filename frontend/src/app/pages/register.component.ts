import { Component, OnDestroy, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService, UsernameCheck } from '../core/api.service';
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
              <input id="u" name="username" [(ngModel)]="form.username" (ngModelChange)="onUsername($event)"
                     autocomplete="username" autocapitalize="none" spellcheck="false" maxlength="30" required
                     [class.ok]="check()?.available" [class.bad]="check() && !check()!.available" />
              @let c = check();
              @if (checking()) {
                <small class="u-state">{{ i.t('acc.checking') }}</small>
              } @else if (c) {
                @if (c.available) {
                  <small class="u-state ok">✓ {{ i.t('acc.free') }}</small>
                } @else {
                  <small class="u-state bad">{{ i.t('acc.err.' + c.code) }}</small>
                  @if (c.suggestions?.length) {
                    <div class="sugg">
                      <span>{{ i.t('acc.try') }}</span>
                      @for (s of c.suggestions; track s) {
                        <button type="button" (click)="pick(s)">{{ s }}</button>
                      }
                    </div>
                  }
                }
              } @else {
                <small class="hint">{{ i.t('acc.rules') }}</small>
              }
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
                  [disabled]="busy()">{{ i.t('auth.register') }}</button>
          <p class="switch">{{ i.t('auth.haveAccount') }} <a routerLink="/login" [queryParams]="{ returnUrl: returnUrl() || '/' }">{{ i.t('auth.login') }}</a></p>
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
    input.ok { border-color: #1f9d55; }
    input.bad { border-color: #d64545; }
    .u-state { display: block; margin-top: .35rem; font-size: .8rem; color: var(--muted); }
    .u-state.ok { color: #1f9d55; font-weight: 600; }
    .u-state.bad { color: #c03b3b; }
    .sugg { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; margin-top: .45rem; font-size: .78rem; color: var(--muted); }
    .sugg button { border: 1.5px solid var(--line); background: var(--surface, #fff); color: var(--text); border-radius: 999px;
                   padding: .25em .75em; font: 600 .78rem var(--font-body); cursor: pointer; }
    .sugg button:hover { border-color: var(--green-700); color: var(--green-700); }
    @media (max-width: 720px) { .auth { grid-template-columns: 1fr; } .side { height: 140px; } .two { grid-template-columns: 1fr; } }
  `],
})
export class RegisterComponent implements OnDestroy {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private router = inject(Router);

  readonly returnUrl = input<string>('/');
  form = { first_name: '', username: '', email: '', password: '' };
  readonly busy = signal(false);
  readonly errors = signal<string[]>([]);
  readonly check = signal<UsernameCheck | null>(null);
  readonly checking = signal(false);
  private timer?: ReturnType<typeof setTimeout>;

  /** checks the username while the customer types (after a short pause) */
  onUsername(value: string) {
    clearTimeout(this.timer);
    this.check.set(null);
    const v = value.trim();
    if (!v) { this.checking.set(false); return; }
    this.checking.set(true);
    this.timer = setTimeout(() => {
      this.api.usernameCheck(v).subscribe({
        next: r => { if (this.form.username.trim() === v) { this.check.set(r); this.checking.set(false); } },
        error: () => this.checking.set(false),
      });
    }, 400);
  }

  pick(name: string) {
    this.form.username = name;
    this.onUsername(name);
  }

  ngOnDestroy() {
    clearTimeout(this.timer);
  }

  submit() {
    if (!this.form.username.trim() || !this.form.email.trim() || !this.form.password) {
      this.errors.set([this.i.t('auth.fillFields')]);
      return;
    }
    const c = this.check();
    if (c && !c.available) {
      this.errors.set([this.i.t('acc.err.' + c.code)]);
      return;
    }
    this.busy.set(true);
    this.errors.set([]);
    this.auth.register(this.form).subscribe({
      next: () => this.router.navigateByUrl(this.returnUrl() || '/'),
      error: e => {
        this.busy.set(false);
        const body = e.error && typeof e.error === 'object' ? e.error : null;
        const msgs = body ? Object.values(body).flat().map(String) : [this.i.t('common.error')];
        this.errors.set(msgs.length ? msgs : [this.i.t('common.error')]);
      },
    });
  }
}
