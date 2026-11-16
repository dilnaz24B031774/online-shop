import { Component, OnInit, computed, inject, input, signal, effect } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { CurrencyService } from '../core/currency.service';
import { Category, Product, ProductFilters } from '../core/models';
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

        <div class="filters">
          <div class="f-head">
            <h3>{{ i.t('filter.title') }}</h3>
            @if (hasFilters()) {
              <button type="button" class="link" (click)="resetFilters()">{{ i.t('filter.reset') }}</button>
            }
          </div>

          <fieldset>
            <legend>{{ priceLabel() }}</legend>
            <div class="price">
              <input type="number" min="0" step="0.01" [placeholder]="i.t('filter.from') + ' ' + money.inputValue(options()?.min_price)"
                     [ngModel]="money.inputValue(min_price())" (change)="setPriceParam('min_price', $any($event.target).value)"
                     [attr.aria-label]="priceLabel() + ' ' + i.t('filter.from')" />
              <span>–</span>
              <input type="number" min="0" step="0.01" [placeholder]="i.t('filter.to') + ' ' + money.inputValue(options()?.max_price)"
                     [ngModel]="money.inputValue(max_price())" (change)="setPriceParam('max_price', $any($event.target).value)"
                     [attr.aria-label]="priceLabel() + ' ' + i.t('filter.to')" />
            </div>
          </fieldset>

          @if (options()?.brands?.length) {
            <fieldset>
              <legend>{{ i.t('filter.brand') }}</legend>
              <div class="brands">
                @for (b of options()!.brands; track b.brand) {
                  <label class="check">
                    <input type="checkbox" [checked]="selectedBrands().includes(b.brand)" (change)="toggleBrand(b.brand)" />
                    <span>{{ b.brand }}</span><small>{{ b.count }}</small>
                  </label>
                }
              </div>
            </fieldset>
          }

          <fieldset>
            <legend>{{ i.t('filter.rating') }}</legend>
            <div class="rating">
              @for (r of ratings; track r) {
                <button type="button" [class.on]="(min_rating() ?? '') === r" (click)="setParam('min_rating', r)">
                  {{ r ? '★ ' + r + '+' : i.t('filter.any') }}
                </button>
              }
            </div>
          </fieldset>

          <label class="check stock">
            <input type="checkbox" [checked]="in_stock() === '1'" (change)="setParam('in_stock', $any($event.target).checked ? '1' : '')" />
            <span>{{ i.t('filter.inStock') }}</span>
          </label>
        </div>
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
              <option value="rating">{{ i.t('sort.rating') }}</option>
              <option value="popular">{{ i.t('sort.popular') }}</option>
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
    .side { position: sticky; top: 180px; max-height: calc(100vh - 200px); overflow-y: auto; border: 1px solid var(--line); border-radius: var(--r-lg); padding: 1.2rem; }
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
    .filters { border-top: 1px solid var(--line); margin-top: 1rem; padding-top: 1rem; display: flex; flex-direction: column; gap: 1rem; }
    .f-head { display: flex; justify-content: space-between; align-items: baseline; }
    .f-head h3 { font-size: 1rem; margin: 0; }
    .link { border: 0; background: none; color: var(--green-700); font-weight: 600; font-size: .84rem; cursor: pointer; padding: 0; }
    fieldset { border: 0; margin: 0; padding: 0; }
    legend { font-weight: 700; font-size: .88rem; margin-bottom: .5rem; padding: 0; }
    .price { display: grid; grid-template-columns: 1fr auto 1fr; gap: .4rem; align-items: center; }
    .price input { width: 100%; padding: .5em .6em; min-width: 0; }
    .brands { display: flex; flex-direction: column; gap: .3rem; max-height: 210px; overflow-y: auto; }
    .check { display: flex; align-items: center; gap: .55rem; margin: 0; font-weight: 500; font-size: .9rem; cursor: pointer; }
    .check input { width: 17px; height: 17px; accent-color: var(--green-700); margin: 0; }
    .check small { margin-left: auto; color: var(--ink-soft); }
    .rating { display: flex; flex-wrap: wrap; gap: .35rem; }
    .rating button {
      border: 1px solid var(--line); background: #fff; border-radius: 999px; padding: .35em .8em;
      font: 600 .82rem var(--font-body); cursor: pointer; color: var(--ink);
    }
    .rating button.on { background: var(--green-700); border-color: var(--green-700); color: #fff; }
    @media (max-width: 800px) {
      .layout { grid-template-columns: 1fr; }
      .side { position: static; }
      .cats { flex-direction: row; overflow-x: auto; }
      .cats a { white-space: nowrap; gap: .6rem; }
      .brands { flex-direction: row; flex-wrap: wrap; max-height: none; gap: .3rem 1rem; }
    }
  `],
})
export class CatalogComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly money = inject(CurrencyService);
  private api = inject(ApiService);
  private router = inject(Router);

  // read from the address bar: /catalog?category=1&q=mouse&sort=price
  readonly category = input<string>();
  readonly q = input<string>();
  readonly sort = input<string>();
  readonly brand = input<string>();
  readonly min_price = input<string>();
  readonly max_price = input<string>();
  readonly min_rating = input<string>();
  readonly in_stock = input<string>();

  readonly ratings = ['', '3', '4', '4.5'];
  readonly priceLabel = computed(() => this.i.t('filter.price').replace(/,?\s*\$$/, '') + ', ' + this.money.currency());
  readonly options = signal<ProductFilters | null>(null);
  readonly selectedBrands = computed(() => (this.brand() ?? '').split(',').filter(Boolean));
  readonly hasFilters = computed(() =>
    !!(this.brand() || this.min_price() || this.max_price() || this.min_rating() || this.in_stock()));

  readonly categories = signal<Category[]>([]);
  readonly products = signal<Product[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);
  readonly String = String;
  readonly total = computed(() => this.categories().reduce((s, c) => s + (c.product_count ?? 0), 0));

  constructor() {
    effect(() => {
      const filter = {
        category: this.category(), q: this.q(), sort: this.sort(), brand: this.brand(),
        min_price: this.min_price(), max_price: this.max_price(), min_rating: this.min_rating(),
        in_stock: this.in_stock(),
      };
      this.loading.set(true);
      this.api.products(filter).subscribe({
        next: p => { this.products.set(p); this.loading.set(false); this.error.set(false); },
        error: () => { this.loading.set(false); this.error.set(true); },
      });
    });
    // brands and price range of the chosen category
    effect(() => {
      this.api.productFilters(this.category()).subscribe({ next: o => this.options.set(o), error: () => {} });
    });
  }

  ngOnInit() {
    this.api.categories().subscribe(c => this.categories.set(c));
  }

  setParam(name: string, value: string) {
    this.router.navigate([], { queryParams: { [name]: value || null }, queryParamsHandling: 'merge' });
  }

  setPriceParam(name: 'min_price' | 'max_price', value: string) {
    // Keep URLs and API bounds in USD so changing display currency never changes the result set.
    if (!value.trim()) { this.setParam(name, ''); return; }
    const amount = Number(value);
    if (!Number.isFinite(amount) || amount < 0) return;
    this.setParam(name, String(Number(this.money.toBase(amount).toFixed(6))));
  }

  toggleBrand(brand: string) {
    const list = this.selectedBrands();
    const next = list.includes(brand) ? list.filter(b => b !== brand) : [...list, brand];
    this.setParam('brand', next.join(','));
  }

  resetFilters() {
    this.router.navigate([], {
      queryParams: { brand: null, min_price: null, max_price: null, min_rating: null, in_stock: null },
      queryParamsHandling: 'merge',
    });
  }

  changeSort(sort: string) {
    this.router.navigate([], { queryParams: { sort: sort || null }, queryParamsHandling: 'merge' });
  }
}
