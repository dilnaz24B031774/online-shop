import { Component, effect, inject, input, signal } from '@angular/core';
import { DOCUMENT, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { ProductDetail } from '../core/models';
import { ProductImageComponent } from '../shared/product-image.component';
import { StarsComponent } from '../shared/stars.component';
import { FavoritesService } from '../core/favorites.service';
import { NotifyButtonComponent } from '../shared/notify-button.component';

@Component({
  selector: 'app-product',
  imports: [RouterLink, FormsModule, DatePipe, ProductImageComponent, StarsComponent, NotifyButtonComponent],
  template: `
    <div class="container page">
      <a routerLink="/catalog" class="back">← {{ i.t('product.back') }}</a>

      @if (product(); as p) {
        <div class="top">
          <div class="art">
            <app-product-image [product]="p" />
          </div>

          <div class="info">
            <a class="chip" [routerLink]="['/catalog']" [queryParams]="{ category: p.category.id }">{{ i.pick(p.category) }}</a>
            <h1>{{ i.pick(p) }}</h1>
            <app-stars [value]="p.avg_rating" [count]="p.review_count" />

            <div class="actions">
              <button type="button" class="like-btn" [class.on]="fav.isLiked(p.id)" (click)="toggleLike(p.id)">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.5-9.2C1 8 3.4 4.5 7 4.5c2 0 3.5 1 5 3 1.5-2 3-3 5-3 3.6 0 6 3.5 4.5 7.3C19.5 16.4 12 21 12 21z"/></svg>
                {{ fav.isLiked(p.id) ? i.t('product.unlike') : i.t('product.like') }}
              </button>

              <!-- opens WhatsApp with the product name, price and link -->
              <a class="share-btn" [href]="waLink(p)" target="_blank" rel="noopener noreferrer">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3a9 9 0 0 0-7.8 13.5L3 21l4.6-1.2A9 9 0 1 0 12 3z"/><path d="M9 8.5c0 3 3.5 6.5 6.5 6.5l1-1.5-2-1-1 .8c-1-.4-2-1.4-2.4-2.4l.8-1-1-2z"/></svg>
                {{ i.t('product.share') }}
              </a>
            </div>

            <p class="desc">{{ i.pick(p, 'description') }}</p>
            <p class="muted small">@if (p.brand) { {{ i.t('product.brand') }}: <strong>{{ p.brand }}</strong> · }{{ i.t('product.code') }}: {{ p.sku }}</p>

            <div class="buy panel">
              <div class="price-row">
                <span class="price">\${{ p.price }}</span>
                @if (p.stock_quantity === 0) {
                  <span class="stock out">{{ i.t('product.soldOut') }}</span>
                } @else if (p.stock_quantity < 10) {
                  <span class="stock low">{{ i.t('product.left', { n: p.stock_quantity }) }}</span>
                } @else {
                  <span class="stock ok">{{ i.t('product.inStock') }}</span>
                }
              </div>

              @if (p.stock_quantity > 0) {
                <div class="buy-row">
                  <div class="stepper">
                    <button type="button" (click)="qty.set(qty() - 1)" [disabled]="qty() <= 1" aria-label="−">−</button>
                    <span>{{ qty() }}</span>
                    <button type="button" (click)="qty.set(qty() + 1)" [disabled]="qty() >= p.stock_quantity" aria-label="+">+</button>
                  </div>
                  <button class="btn btn-sun grow" type="button" (click)="addToCart(p)" [disabled]="busy()">
                    {{ auth.isLoggedIn() ? i.t('product.add') : i.t('product.loginToBuy') }}
                  </button>
                </div>
                @if (cart.quantityOf(p.id) > 0) {
                  <p class="in-cart">{{ i.t('product.added') }}: {{ cart.quantityOf(p.id) }} · <a routerLink="/cart">{{ i.t('nav.cart') }}</a></p>
                }
              }
              @if (p.stock_quantity === 0) {
                <app-notify-button [productId]="p.id" size="big" />
              }
              @if (cartError()) { <div class="alert alert-error">{{ cartError() }}</div> }
            </div>
          </div>
        </div>

        <section class="reviews">
          <h2>{{ i.t('product.reviews') }} ({{ p.reviews.length }})</h2>
          <div class="rev-grid">
            <div class="list">
              @for (r of p.reviews; track r.id) {
                <article class="review panel">
                  <header>
                    <span class="who">{{ r.username }}</span>
                    <app-stars [value]="r.rating" />
                  </header>
                  @if (r.comment) { <p>{{ r.comment }}</p> }
                  <small class="muted">{{ r.created_at | date: 'mediumDate' }}</small>
                </article>
              } @empty {
                <p class="muted">{{ i.t('product.noReviews') }}</p>
              }
            </div>

            @if (auth.isLoggedIn()) {
              <form class="panel write" (ngSubmit)="sendReview(p.id)">
                <h3>{{ i.t('product.writeReview') }}</h3>
                <label>{{ i.t('product.rating') }}</label>
                <div class="rate" role="radiogroup">
                  @for (s of [1,2,3,4,5]; track s) {
                    <button type="button" [class.on]="s <= rating()" (click)="rating.set(s)" [attr.aria-label]="s">★</button>
                  }
                </div>
                <div class="field">
                  <label for="comment">{{ i.t('product.comment') }}</label>
                  <textarea id="comment" name="comment" rows="3" [(ngModel)]="comment"></textarea>
                </div>
                @if (reviewMsg()) { <div class="alert" [class.alert-ok]="reviewOk()" [class.alert-error]="!reviewOk()">{{ reviewMsg() }}</div> }
                <button class="btn btn-primary" type="submit">{{ i.t('product.sendReview') }}</button>
              </form>
            }
          </div>
        </section>
      } @else if (error()) {
        <div class="alert alert-error">{{ i.t('common.error') }}</div>
      } @else {
        <p class="muted">{{ i.t('common.loading') }}</p>
      }
    </div>
  `,
  styles: [`
    .back { display: inline-block; margin-bottom: 1.2rem; font-weight: 600; }
    .top { display: grid; grid-template-columns: 1fr 1fr; gap: 2.5rem; align-items: start; }
    .art { border-radius: 18px; overflow: hidden; height: 460px; background: var(--soft); padding: 2rem; border: 1px solid var(--line); }

    h1 { font-size: clamp(1.8rem, 3.4vw, 2.6rem); margin: .6rem 0 .4rem; }
    .chip { text-decoration: none; }
    .desc { margin-top: 1rem; font-size: 1.08rem; }
    .small { font-size: .88rem; }
    .buy { margin-top: 1.2rem; }
    .price-row { display: flex; align-items: center; justify-content: space-between; gap: 1rem; margin-bottom: 1rem; }
    .price { font-family: var(--font-display); font-size: 2rem; font-weight: 700; }
    .stock { font-weight: 700; font-size: .9rem; padding: .3em .8em; border-radius: 999px; }
    .stock.ok { background: #e3f4ea; color: var(--ok); }
    .stock.low { background: #fdf0d5; color: var(--warn); }
    .stock.out { background: #fbe9ec; color: var(--berry); }
    .buy-row { display: flex; gap: .8rem; }
    .grow { flex: 1; }
    .stepper { display: flex; align-items: center; background: var(--sky); border-radius: 999px; }
    .stepper button {
      width: 44px; height: 44px; border: 0; background: transparent; font-size: 1.3rem; cursor: pointer; color: var(--ink);
    }
    .stepper button:disabled { opacity: .35; cursor: default; }
    .stepper span { min-width: 28px; text-align: center; font-weight: 700; }
    .in-cart { margin: .8rem 0 0; color: var(--teal-dark); font-weight: 600; }
    .alert { margin-top: 1rem; margin-bottom: 0; }

    .reviews { margin-top: 3rem; }
    .rev-grid { display: grid; grid-template-columns: 1.4fr 1fr; gap: 1.5rem; align-items: start; }
    .list { display: flex; flex-direction: column; gap: 1rem; }
    .review { padding: 1.1rem 1.3rem; }
    .review header { display: flex; justify-content: space-between; align-items: center; margin-bottom: .4rem; }
    .review p { margin: 0 0 .4rem; }
    .who { font-weight: 700; }
    .write h3 { margin-bottom: 1rem; }
    .rate { display: flex; gap: 4px; margin-bottom: 1rem; }
    .rate button {
      font-size: 1.7rem; line-height: 1; border: 0; background: none; cursor: pointer; color: #d6e4ea; padding: 0 2px;
    }
    .rate button.on { color: var(--sun); }
    @media (max-width: 860px) {
      .top, .rev-grid { grid-template-columns: 1fr; }
      .art { height: 280px; }
    }

    .actions { display: flex; flex-wrap: wrap; gap: .6rem; margin-top: .8rem; }
    .like-btn, .share-btn {
      display: inline-flex; align-items: center; gap: .5rem; cursor: pointer; text-decoration: none;
      border: 1.5px solid var(--line); background: #fff; color: var(--text);
      font: 600 .9rem var(--font-body); padding: .5em 1em; border-radius: 999px;
    }
    .like-btn svg { width: 20px; height: 20px; fill: none; stroke: var(--red); stroke-width: 2; stroke-linejoin: round; }
    .like-btn.on { border-color: var(--red); }
    .like-btn.on svg { fill: var(--red); }
    .share-btn svg { width: 20px; height: 20px; fill: none; stroke: #25D366; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .share-btn:hover { border-color: #25D366; }
  `],
})
export class ProductComponent {
  readonly i = inject(I18nService);
  readonly auth = inject(AuthService);
  readonly cart = inject(CartService);
  private api = inject(ApiService);
  private router = inject(Router);
  private doc = inject(DOCUMENT);

  readonly id = input.required<string>();   // from /product/:id

  readonly product = signal<ProductDetail | null>(null);
  readonly error = signal(false);
  readonly qty = signal(1);
  readonly busy = signal(false);
  readonly cartError = signal('');

  readonly rating = signal(5);
  comment = '';
  readonly reviewMsg = signal('');
  readonly reviewOk = signal(false);
  readonly fav = inject(FavoritesService);

  constructor() {
    effect(() => this.load(Number(this.id())));
  }

  load(id: number) {
    this.api.product(id).subscribe({
      next: p => { this.product.set(p); this.qty.set(1); },
      error: () => this.error.set(true),
    });
  }

  addToCart(p: ProductDetail) {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.busy.set(true);
    this.cartError.set('');
    this.cart.add(p.id, this.qty()).subscribe({
      next: () => this.busy.set(false),
      error: e => { this.busy.set(false); this.cartError.set(e.error?.detail ?? this.i.t('common.error')); },
    });
  }

  sendReview(productId: number) {
    this.api.addReview(productId, this.rating(), this.comment).subscribe({
      next: () => {
        this.reviewOk.set(true);
        this.reviewMsg.set(this.i.t('product.reviewSent'));
        this.comment = '';
        this.load(productId);
      },
      error: e => {
        this.reviewOk.set(false);
        this.reviewMsg.set(e.error?.detail ?? e.error?.rating?.[0] ?? this.i.t('common.error'));
      },
    });
  }

  toggleLike(productId: number) {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.fav.toggle(productId).subscribe({ error: () => {} });
  }

  /** Link that opens WhatsApp: "<name> — $<price>" and the address of this product page. */
  waLink(p: ProductDetail): string {
    const url = `${this.doc.location.origin}/product/${p.id}`;
    const text = `${this.i.pick(p)} — $${p.price}\n${url}`;
    return `https://wa.me/?text=${encodeURIComponent(text)}`;
  }
}
