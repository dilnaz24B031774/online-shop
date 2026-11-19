import { Component, OnInit, computed, effect, inject, input, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { FavoritesService } from '../core/favorites.service';
import { I18nService, Lang } from '../core/i18n.service';
import { Address } from '../core/models';
import { ProductCardComponent } from '../shared/product-card.component';
import { OrdersComponent } from './orders.component';

/**
 * Profile area with three SEPARATE tabs:
 *   /profile?tab=profile    personal data + addresses
 *   /profile?tab=orders     my orders
 *   /profile?tab=favorites  liked products
 */
@Component({
  selector: 'app-profile',
  imports: [FormsModule, RouterLink, ProductCardComponent, OrdersComponent],
  template: `
    <div class="container page">
      <h1>{{ i.t('profile.title') }}</h1>

      <div class="layout">
        <aside class="panel me">
          <span class="avatar">{{ initial() }}</span>
          <strong>{{ auth.user()?.first_name || auth.user()?.username }}</strong>
          <span class="muted">{{ auth.user()?.email }}</span>

          <a routerLink="/profile" [queryParams]="{ tab: 'profile' }" class="btn btn-ghost btn-block"
             [class.on]="view() === 'profile'">{{ i.t('profile.tabProfile') }}</a>
          <a routerLink="/profile" [queryParams]="{ tab: 'orders' }" class="btn btn-ghost btn-block"
             [class.on]="view() === 'orders'">{{ i.t('nav.orders') }}</a>
          <a routerLink="/profile" [queryParams]="{ tab: 'favorites' }" class="btn btn-ghost btn-block"
             [class.on]="view() === 'favorites'">{{ i.t('profile.favorites') }}
            @if (fav.count() > 0) { <span class="badge">{{ fav.count() }}</span> }
          </a>
          <a routerLink="/cart" class="btn btn-ghost btn-block">{{ i.t('nav.cart') }}</a>
        </aside>

        <div class="main">
          @switch (view()) {
            @case ('orders') {
              <app-orders />
            }

            @case ('favorites') {
              <section class="favs" id="favorites">
                <h2>{{ i.t('profile.favorites') }} <small>{{ fav.count() }}</small></h2>
                @if (fav.items().length) {
                  <div class="grid">
                    @for (p of fav.items(); track p.id) { <app-product-card [product]="p" /> }
                  </div>
                } @else {
                  <div class="panel empty">
                    <p>{{ i.t('profile.noFavorites') }}</p>
                    <a routerLink="/catalog" class="btn btn-primary">{{ i.t('hero.shop') }}</a>
                  </div>
                }
              </section>
            }

            @default {
              <form class="panel" (ngSubmit)="save()">
                <h2>{{ i.t('profile.account') }}</h2>
                @if (message()) { <div class="alert" [class.alert-ok]="ok()" [class.alert-error]="!ok()">{{ message() }}</div> }
                <div class="two">
                  <div class="field">
                    <label for="fn">{{ i.t('auth.name') }}</label>
                    <input id="fn" name="first_name" [(ngModel)]="form.first_name" autocomplete="given-name" />
                  </div>
                  <div class="field">
                    <label for="ln">{{ i.t('profile.lastName') }}</label>
                    <input id="ln" name="last_name" [(ngModel)]="form.last_name" autocomplete="family-name" />
                  </div>
                  <div class="field">
                    <label for="ph">{{ i.t('profile.phone') }}</label>
                    <input id="ph" name="phone" [(ngModel)]="form.phone" autocomplete="tel" />
                  </div>
                  <div class="field">
                    <label for="lg">{{ i.t('profile.language') }}</label>
                    <select id="lg" name="preferred_language" [(ngModel)]="form.preferred_language">
                      <option value="en">English</option>
                      <option value="ru">Русский</option>
                      <option value="kk">Қазақша</option>
                    </select>
                  </div>
                </div>
                <button class="btn btn-primary" type="submit" [disabled]="busy()">{{ i.t('profile.save') }}</button>
              </form>

              <section class="panel">
                <h2>{{ i.t('profile.addresses') }}</h2>
                @for (a of addresses(); track a.id) {
                  <p class="addr"><strong>{{ a.label }}</strong><br>
                    <span class="muted">{{ a.city }}, {{ a.street }}{{ a.apartment ? ', ' + a.apartment : '' }}</span></p>
                } @empty {
                  <p class="muted">{{ i.t('profile.noAddresses') }}</p>
                }
              </section>
            }
          }
        </div>
      </div>
    </div>
  `,
  styles: [`
    .layout { display: grid; grid-template-columns: 280px 1fr; gap: 1.6rem; align-items: start; }
    .me { display: flex; flex-direction: column; align-items: center; gap: .5rem; text-align: center; }
    .avatar {
      width: 72px; height: 72px; border-radius: 50%; background: var(--green-50); color: var(--green-700);
      display: grid; place-items: center; font-size: 1.8rem; font-weight: 700; margin-bottom: .4rem;
    }
    .me .btn { margin-top: .3rem; }
    .me .btn.on { background: var(--green-700); border-color: var(--green-700); color: #fff; }
    .badge {
      display: inline-grid; place-items: center; min-width: 22px; height: 22px; padding: 0 6px; margin-left: .4rem;
      border-radius: 999px; background: var(--amber); color: var(--green-900); font-size: .78rem; font-weight: 700;
    }
    .main { display: flex; flex-direction: column; gap: 1.2rem; min-width: 0; }
    .two { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; }
    .addr { margin: 0 0 .7rem; }
    .favs h2 small { font-family: var(--font-body); font-size: .9rem; color: var(--ink-soft); font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 16px; }
    .empty { text-align: center; }
    @media (max-width: 820px) {
      .layout { grid-template-columns: 1fr; }
      .two { grid-template-columns: 1fr; }
    }
  `],
})
export class ProfileComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly auth = inject(AuthService);
  readonly fav = inject(FavoritesService);
  private api = inject(ApiService);

  /** from the address bar: /profile?tab=orders  (bound by withComponentInputBinding) */
  readonly tab = input<string | undefined>('profile');
  readonly view = computed<'profile' | 'orders' | 'favorites'>(() => {
    const t = this.tab();
    return t === 'orders' || t === 'favorites' ? t : 'profile';
  });

  readonly addresses = signal<Address[]>([]);
  readonly busy = signal(false);
  readonly message = signal('');
  readonly ok = signal(false);
  form = { first_name: '', last_name: '', phone: '', preferred_language: 'en' };

  constructor() {
    // the user may arrive after a page reload, so fill the form when the data is ready
    effect(() => {
      const u = this.auth.user();
      if (u) this.form = {
        first_name: u.first_name, last_name: u.last_name, phone: u.phone, preferred_language: u.preferred_language,
      };
    });
  }

  ngOnInit() {
    this.fav.load().subscribe({ error: () => {} });
    this.api.addresses().subscribe({ next: a => this.addresses.set(a), error: () => {} });
  }

  initial(): string {
    const u = this.auth.user();
    return (u?.first_name || u?.username || '?').charAt(0).toUpperCase();
  }

  save() {
    this.busy.set(true);
    this.message.set('');
    this.api.updateMe(this.form as any).subscribe({
      next: u => {
        this.auth.user.set(u);
        this.i.use(u.preferred_language as Lang);
        this.ok.set(true);
        this.message.set(this.i.t('profile.saved'));
        this.busy.set(false);
      },
      error: () => { this.ok.set(false); this.message.set(this.i.t('common.error')); this.busy.set(false); },
    });
  }
}
