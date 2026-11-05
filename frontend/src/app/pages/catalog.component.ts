import { Component, OnInit, computed, inject, input, signal, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Category, Product } from '../core/models';
import { ProductCardComponent } from '../shared/product-card.component';

@Component({
  selector: 'app-catalog',
  imports: [RouterLink, FormsModule, ProductCardComponent],
  template: `
    <div class="container page layout">
      <aside class="side">
        <h2>{{ i.t('catalog.title') }}</h2>
        <nav class="cats">
          <a [routerLink]="['/catalog']" [queryParams]="{ q: q() || null, sort: sort() || null }"
             [class.on]="!category()">
            <span>{{ i.t('catalog.all') }}</span><small>{{ total() }}</small>
          </a>
          @for (c of categories(); track c.id) {
            <a [routerLink]="['/catalog']" [queryParams]="{ category: c.id, q: q() || null, sort: sort() || null }"
               [class.on]="category() === String(c.id)">
              <span>{{ i.pick(c) }}</span><small>{{ c.product_count }}</small>
            </a>
          }
        </nav>
      </aside>

      <section>
        <div class="toolbar">
          <p class="found">
            {{ i.t('catalog.found') }}: <strong>{{ products().length }}</strong>
            @if (q()) { · «{{ q() }}» }
          </p>
          <label class="sort">
            <span>{{ i.t('catalog.sort') }}</span>
            <select [ngModel]="sort() || ''" (ngModelChange)="changeSort($event)">
              <option value="">{{ i.t('sort.default') }}</option>
              <option value="price">{{ i.t('sort.price') }}</option>
              <option value="-price">{{ i.t('sort.-price') }}</option>
              <option value="name">{{ i.t('sort.name') }}</option>
            </select>
          </label>
        </div>

        @if (loading()) {
          <p class="muted">{{ i.t('common.loading') }}</p>
        } @else if (error()) {
          <div class="alert alert-error">{{ i.t('common.error') }}</div>
        } @else if (products().length === 0) {
          <div class="panel empty">
            <p>{{ i.t('catalog.empty') }}</p>
            <a routerLink="/catalog" class="btn btn-primary">{{ i.t('catalog.all') }}</a>
          </div>
        } @else {
          <div class="grid">
            @for (p of products(); track p.id) { <app-product-card [product]="p" /> }
          </div>
        }
      </section>
    </div>
  `,
  styles: [`
    .layout { display: grid; grid-template-columns: 240px 1fr; gap: 2rem; align-items: start; }
    .side { position: sticky; top: 180px; border: 1px solid var(--line); border-radius: var(--r-lg); padding: 1.2rem; }
    .side h2 { font-size: 1.2rem; }
    .cats { display: flex; flex-direction: column; gap: 4px; }
    .cats a {
      display: flex; justify-content: space-between; padding: .65rem .9rem; border-radius: 12px;
      color: var(--ink); font-weight: 600; text-decoration: none;
    }
    .cats a small { color: var(--ink-soft); font-weight: 500; }
    .cats a:hover { background: var(--soft); }
    .cats a.on { background: var(--green-700); color: #fff; }
    .cats a.on small { color: #cfe5db; }
    .toolbar { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-bottom: 1.2rem; flex-wrap: wrap; }
    .found { margin: 0; }
    .sort { display: flex; align-items: center; gap: .6rem; margin: 0; font-weight: 500; }
    .sort select { width: auto; padding: .5em .8em; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 16px; }
    .empty { text-align: center; }
    @media (max-width: 800px) {
      .layout { grid-template-columns: 1fr; }
      .side { position: static; }
      .cats { flex-direction: row; overflow-x: auto; }
      .cats a { white-space: nowrap; gap: .6rem; }
    }
  `],
})
export class CatalogComponent implements OnInit {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private router = inject(Router);

  // read from the address bar: /catalog?category=1&q=mouse&sort=price
  readonly category = input<string>();
  readonly q = input<string>();
  readonly sort = input<string>();

  readonly categories = signal<Category[]>([]);
  readonly products = signal<Product[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);
  readonly String = String;
  readonly total = computed(() => this.categories().reduce((s, c) => s + (c.product_count ?? 0), 0));

  constructor() {
    effect(() => {
      const filter = { category: this.category(), q: this.q(), sort: this.sort() };
      this.loading.set(true);
      this.api.products(filter).subscribe({
        next: p => { this.products.set(p); this.loading.set(false); this.error.set(false); },
        error: () => { this.loading.set(false); this.error.set(true); },
      });
    });
  }

  ngOnInit() {
    this.api.categories().subscribe(c => this.categories.set(c));
  }

  changeSort(sort: string) {
    this.router.navigate([], { queryParams: { sort: sort || null }, queryParamsHandling: 'merge' });
  }
}
