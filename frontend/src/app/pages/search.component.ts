import { Component, effect, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { SearchResult } from '../core/models';
import { ProductCardComponent } from '../shared/product-card.component';

/** Search across three entity types: products, categories and the user's orders. */
@Component({
  selector: 'app-search',
  imports: [RouterLink, DatePipe, ProductCardComponent],
  template: `
    <div class="container page">
      <h1 class="title">{{ i.t('search.title') }} «{{ q() }}»</h1>

      @if (result(); as r) {
        @if (!r.products.length && !r.categories.length && !r.orders.length) {
          <div class="panel"><p>{{ i.t('search.none') }}</p>
            <a routerLink="/catalog" class="btn btn-primary">{{ i.t('catalog.all') }}</a></div>
        }

        @if (r.categories.length) {
          <section>
            <h2>{{ i.t('search.categories') }} <small>{{ r.categories.length }}</small></h2>
            <div class="cats">
              @for (c of r.categories; track c.id) {
                <a class="cat" [routerLink]="['/catalog']" [queryParams]="{ category: c.id }">{{ i.pick(c) }}</a>
              }
            </div>
          </section>
        }

        @if (r.products.length) {
          <section>
            <h2>{{ i.t('search.products') }} <small>{{ r.products.length }}</small></h2>
            <div class="grid">
              @for (p of r.products; track p.id) { <app-product-card [product]="p" /> }
            </div>
          </section>
        }

        @if (r.orders.length) {
          <section>
            <h2>{{ i.t('search.orders') }} <small>{{ r.orders.length }}</small></h2>
            <div class="orders">
              @for (o of r.orders; track o.id) {
                <a class="order panel" routerLink="/orders">
                  <strong>{{ i.t('orders.order') }} #{{ o.id }}</strong>
                  <span class="muted">{{ o.created_at | date: 'mediumDate' }}</span>
                  <span>{{ i.t('status.' + o.status) }}</span>
                  <strong>\${{ o.total_amount }}</strong>
                </a>
              }
            </div>
          </section>
        }
      } @else if (error()) {
        <div class="alert alert-error">{{ i.t('common.error') }}</div>
      } @else {
        <p class="muted">{{ i.t('common.loading') }}</p>
      }
    </div>
  `,
  styles: [`
    .title { font-size: clamp(1.6rem, 3vw, 2.2rem); }
    section { margin-top: 2rem; }
    h2 small { font-family: var(--font-body); font-size: .9rem; color: var(--ink-soft); font-weight: 600; }
    .cats { display: flex; gap: .6rem; flex-wrap: wrap; }
    .cat { background: var(--green-700); color: #fff; padding: .55em 1.1em; border-radius: 999px; font-weight: 600; text-decoration: none; }
    .cat:hover { background: var(--green-900); }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 1.2rem; }
    .orders { display: flex; flex-direction: column; gap: .7rem; }
    .order { display: grid; grid-template-columns: 1fr 1fr 1fr auto; gap: 1rem; padding: 1rem 1.3rem; color: var(--ink); text-decoration: none; }
  `],
})
export class SearchComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  readonly q = input<string>('');
  readonly result = signal<SearchResult | null>(null);
  readonly error = signal(false);

  constructor() {
    effect(() => {
      const q = this.q() ?? '';
      this.result.set(null);
      this.api.search(q).subscribe({ next: r => this.result.set(r), error: () => this.error.set(true) });
    });
  }
}
