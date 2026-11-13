import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Category, Product } from '../core/models';
import { ProductCardComponent } from '../shared/product-card.component';
import { ProductImageComponent } from '../shared/product-image.component';

@Component({
  selector: 'app-home',
  imports: [RouterLink, ProductCardComponent, ProductImageComponent],
  template: `
    @if (error()) {
      <div class="container"><div class="alert alert-error" style="margin-top:1.5rem">{{ i.t('common.error') }}</div></div>
    }

    <!-- hero banners -->
    <section class="container hero">
      @if (bySku('FA-SUMDR'); as p) {
        <a class="banner big" [routerLink]="['/catalog']" [queryParams]="{ category: p.category.id }">
          <div class="text">
            <span class="tag">{{ i.t('hero1.tag') }}</span>
            <h1>{{ i.t('hero1.title') }}</h1>
            <span class="btn btn-primary">{{ i.t('hero1.cta') }}</span>
          </div>
          <div class="pic"><app-product-image [product]="p" /></div>
        </a>
      }
      @if (bySku('EL-AIRPD'); as p) {
        <a class="banner dark" [routerLink]="['/product', p.id]">
          <div class="text">
            <span class="tag">{{ i.t('hero2.tag') }}</span>
            <h2>{{ i.t('hero2.title') }}</h2>
            <span class="btn btn-sun">{{ i.t('hero2.cta') }} · \${{ p.price }}</span>
          </div>
          <div class="pic"><app-product-image [product]="p" /></div>
        </a>
      }
      @if (bySku('SH-AJ1'); as p) {
        <a class="banner warm" [routerLink]="['/catalog']" [queryParams]="{ category: p.category.id }">
          <div class="text">
            <span class="tag">{{ i.t('hero3.tag') }}</span>
            <h2>{{ i.t('hero3.title') }}</h2>
            <span class="btn btn-primary">{{ i.t('hero3.cta') }}</span>
          </div>
          <div class="pic"><app-product-image [product]="p" /></div>
        </a>
      }
    </section>

    <!-- category circles -->
    <section class="container cats">
      <div class="section-head"><h2>{{ i.t('home.categories') }}</h2></div>
      <div class="cat-row">
        @for (c of categories(); track c.id) {
          <a class="cat" [routerLink]="['/catalog']" [queryParams]="{ category: c.id }">
            <span class="circle">
              @if (coverOf(c); as cover) { <app-product-image [product]="cover" /> }
            </span>
            <strong>{{ i.pick(c) }}</strong>
            <small>{{ c.product_count }} {{ i.t('home.products') }}</small>
          </a>
        }
      </div>
    </section>

    <!-- weekly best sellers on green -->
    <section class="deals">
      <div class="container">
        <div class="deals-head">
          <div>
            <h2>{{ i.t('home.deals') }}</h2>
            <p>{{ i.t('home.dealsText') }}</p>
          </div>
          <div class="tabs" role="tablist">
            <button type="button" role="tab" [class.on]="tab() === 0" (click)="tab.set(0)">{{ i.t('home.tabAll') }}</button>
            @for (c of dealCategories(); track c.id) {
              <button type="button" role="tab" [class.on]="tab() === c.id" (click)="tab.set(c.id)">{{ i.pick(c) }}</button>
            }
          </div>
        </div>
        <div class="grid five">
          @for (p of dealProducts(); track p.id; let idx = $index) {
            <app-product-card [product]="p" [rank]="tab() === 0 ? idx + 1 : null" />
          }
        </div>
      </div>
    </section>

    <!-- promo banners -->
    <section class="container promos">
      @for (promo of promos(); track promo.key) {
        <a class="promo" [class]="'promo ' + promo.tone" [routerLink]="['/catalog']" [queryParams]="{ category: promo.product.category.id }">
          <div class="text">
            <h3>{{ i.t('promo.' + promo.key + '.title') }}</h3>
            <p>{{ i.t('promo.' + promo.key + '.text') }}</p>
            <span class="link">{{ i.t('promo.cta') }}</span>
          </div>
          <div class="pic"><app-product-image [product]="promo.product" /></div>
        </a>
      }
    </section>

    <!-- popular products -->
    <section class="container popular">
      <div class="section-head">
        <h2>{{ i.t('home.new') }}</h2>
        <a routerLink="/catalog" class="btn btn-ghost">{{ i.t('home.viewAll') }}</a>
      </div>
      <div class="grid five">
        @for (p of popular(); track p.id) { <app-product-card [product]="p" /> }
      </div>
    </section>

    <!-- perks -->
    <section class="container perks">
      <div><svg viewBox="0 0 24 24"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19a2 2 0 1 0 0-.1M17 19a2 2 0 1 0 0-.1"/></svg><span>{{ i.t('perk.delivery') }}</span></div>
      <div><svg viewBox="0 0 24 24"><rect x="3" y="6" width="18" height="12" rx="2"/><path d="M3 10h18M7 15h4"/></svg><span>{{ i.t('perk.pay') }}</span></div>
      <div><svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/></svg><span>{{ i.t('perk.lang') }}</span></div>
      <div><svg viewBox="0 0 24 24"><path d="M4 13a8 8 0 0 1 16 0v4a2 2 0 0 1-2 2h-1v-6h3M4 13v4a2 2 0 0 0 2 2h1v-6H4"/></svg><span>{{ i.t('perk.support') }}</span></div>
    </section>
  `,
  styles: [`
    /* hero */
    .hero {
      display: grid; grid-template-columns: 1.55fr 1fr; grid-template-rows: 210px 210px; gap: 18px;
      margin-top: 1.6rem;
    }
    .banner {
      position: relative; border-radius: 18px; overflow: hidden; display: grid;
      grid-template-columns: 1.1fr 1fr; align-items: center; padding: 1.4rem 1.6rem;
      color: var(--text); text-decoration: none !important;
    }
    .banner .text { position: relative; z-index: 1; display: flex; flex-direction: column; align-items: flex-start; gap: .7rem; }
    .banner .pic { height: 100%; min-height: 0; filter: drop-shadow(0 18px 18px rgba(0,0,0,.18)); }
    .banner h1, .banner h2 { margin: 0; }
    .tag {
      font-size: .78rem; font-weight: 700; padding: .3em .75em; border-radius: 6px;
      background: rgba(255,255,255,.75); color: var(--green-700);
    }
    .big { grid-row: span 2; background: linear-gradient(135deg, #e3f1ea 0%, #cfe7dc 100%); padding: 2.4rem; }
    .big h1 { font-size: clamp(1.8rem, 3.2vw, 2.7rem); max-width: 13ch; color: var(--green-900); }
    .big .btn { margin-top: .4rem; }
    .dark { background: var(--green-900); color: #fff; }
    .dark h2 { color: #fff; font-size: 1.35rem; }
    .dark .tag { background: var(--amber); color: var(--green-900); }
    .warm { background: linear-gradient(135deg, #fff1d6 0%, #ffe2ad 100%); }
    .warm h2 { font-size: 1.35rem; color: var(--green-900); }
    .banner:hover .btn-primary { background: var(--green-900); }

    /* categories */
    .cats { margin-top: 2.6rem; }
    .cat-row { display: grid; grid-template-columns: repeat(9, 1fr); gap: 14px; }
    .cat { display: flex; flex-direction: column; align-items: center; text-align: center; gap: .25rem; color: var(--text); text-decoration: none !important; }
    .circle {
      width: 104px; height: 104px; border-radius: 50%; background: var(--soft); border: 2px solid transparent;
      padding: 16px; display: block; transition: border-color .15s, background .15s; margin-bottom: .35rem;
    }
    .cat:hover .circle { border-color: var(--green-700); background: var(--green-50); }
    .cat strong { font-size: .9rem; }
    .cat small { color: var(--muted); font-size: .78rem; }

    /* deals */
    .deals { background: var(--green-900); margin-top: 2.8rem; padding: 2.4rem 0 2.6rem; }
    .deals-head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1rem 2rem; flex-wrap: wrap; margin-bottom: 1.3rem; }
    .deals h2 { color: #fff; margin-bottom: .2rem; }
    .deals p { color: #b9d2c6; margin: 0; }
    .tabs { display: flex; gap: 6px; flex-wrap: wrap; }
    .tabs button {
      border: 1px solid rgba(255,255,255,.22); background: transparent; color: #e3efe9;
      font: 600 .84rem var(--font-body); padding: .45em .95em; border-radius: 999px; cursor: pointer;
    }
    .tabs button:hover { border-color: var(--amber); }
    .tabs button.on { background: var(--amber); border-color: var(--amber); color: var(--green-900); }
    .grid { display: grid; gap: 16px; }
    .grid.five { grid-template-columns: repeat(5, 1fr); }

    /* promos */
    .promos { display: grid; grid-template-columns: repeat(3, 1fr); gap: 18px; margin-top: 2.8rem; }
    .promo {
      border-radius: 16px; overflow: hidden; display: grid; grid-template-columns: 1.1fr 1fr; align-items: center;
      padding: 1.3rem 1.4rem; height: 190px; color: var(--text); text-decoration: none !important;
    }
    .promo h3 { font-size: 1.2rem; font-weight: 700; margin-bottom: .3rem; color: var(--green-900); }
    .promo p { font-size: .88rem; color: var(--muted); margin-bottom: .7rem; }
    .promo .link { font-weight: 700; color: var(--green-700); border-bottom: 2px solid var(--amber); }
    .promo .pic { height: 150px; }
    .mint { background: #e6f2ec; }
    .sand { background: #f6efe6; }
    .sky { background: #e8f0f8; }

    /* popular */
    .popular { margin-top: 2.8rem; }

    /* perks */
    .perks {
      display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-top: 2.8rem;
      border: 1px solid var(--line); border-radius: 16px; padding: 1.2rem 1.4rem;
    }
    .perks div { display: flex; align-items: center; gap: .8rem; font-size: .9rem; font-weight: 500; }
    .perks svg {
      width: 42px; height: 42px; flex: none; padding: 9px; border-radius: 50%; background: var(--green-50);
      fill: none; stroke: var(--green-700); stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round;
    }

    @media (max-width: 1150px) {
      .grid.five { grid-template-columns: repeat(4, 1fr); }
      .cat-row { grid-template-columns: repeat(auto-fill, minmax(100px, 1fr)); }
      .perks { grid-template-columns: repeat(2, 1fr); }
    }
    @media (max-width: 860px) {
      .hero { grid-template-columns: 1fr; grid-template-rows: 300px 190px 190px; }
      .big { grid-row: auto; }
      .grid.five { grid-template-columns: repeat(2, 1fr); }
      .promos { grid-template-columns: 1fr; }
      .circle { width: 86px; height: 86px; }
    }
    @media (max-width: 520px) {
      .banner { padding: 1.1rem; grid-template-columns: 1.5fr .8fr; }
      .promo { grid-template-columns: 1.5fr .8fr; }
      .big { padding: 1.4rem; }
      .big h1 { font-size: 1.6rem; }
      .perks { grid-template-columns: 1fr; }
    }
  `],
})
export class HomeComponent implements OnInit {
  readonly i = inject(I18nService);
  private api = inject(ApiService);

  readonly categories = signal<Category[]>([]);
  readonly products = signal<Product[]>([]);
  readonly bestSellers = signal<Product[]>([]);
  readonly error = signal(false);
  readonly tab = signal(0);   // 0 = all, otherwise category id

  ngOnInit() {
    this.api.categories().subscribe({ next: c => this.categories.set(c), error: () => this.error.set(true) });
    this.api.products().subscribe({ next: p => this.products.set(p), error: () => this.error.set(true) });
    this.api.bestSellers(10).subscribe({ next: p => this.bestSellers.set(p), error: () => this.error.set(true) });
  }

  bySku(sku: string): Product | undefined {
    return this.products().find(p => p.sku === sku);
  }

  /** a product photo that represents the category */
  coverOf(c: Category): Product | undefined {
    const inCat = this.products().filter(p => p.category.id === c.id);
    return inCat.find(p => p.image_url) ?? inCat[0];
  }

  readonly dealCategories = computed(() =>
    this.categories().filter(c => this.products().some(p => p.category.id === c.id && p.image_url)).slice(0, 6));

  readonly dealProducts = computed(() => {
    if (this.tab() === 0) return this.bestSellers().slice(0, 5);
    return this.products().filter(p => p.category.id === this.tab()).slice(0, 5);
  });

  readonly promos = computed(() => {
    const list = [
      { key: 'watch', sku: 'EL-AWS4', tone: 'mint' },
      { key: 'style', sku: 'FA-GOWN', tone: 'sand' },
      { key: 'sport', sku: 'SP-BASKB', tone: 'sky' },
    ];
    return list.map(x => ({ ...x, product: this.bySku(x.sku)! })).filter(x => x.product);
  });

  readonly popular = computed(() => {
    const top = new Set(this.bestSellers().map(p => p.id));
    return this.products()
      .filter(p => p.image_url && !top.has(p.id))
      .sort((a, b) => (b.review_count - a.review_count) || (a.id - b.id))
      .slice(0, 10);
  });
}
