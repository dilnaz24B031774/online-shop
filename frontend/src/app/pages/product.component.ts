import { Component, computed, DestroyRef, effect, inject, input, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { CurrencyService } from '../core/currency.service';
import { ProductDetail } from '../core/models';
import { ProductImageComponent } from '../shared/product-image.component';
import { StarsComponent } from '../shared/stars.component';

@Component({
  selector: 'app-product',
  imports: [RouterLink, FormsModule, DatePipe, ProductImageComponent, StarsComponent],
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
            <p class="desc">{{ i.pick(p, 'description') }}</p>
            <p class="muted small">@if (p.brand) { {{ i.t('product.brand') }}: <strong>{{ p.brand }}</strong> · }{{ i.t('product.code') }}: {{ p.sku }}</p>

            <div class="buy panel">
              <div class="price-row">
                <span class="price">{{ money.format(p.price) }}</span>
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
              @if (hasReviewed()) {
                <aside class="panel write">
                  <h3>{{ i.t('product.writeReview') }}</h3>
                  <p class="muted" role="status">{{ i.t(reviewOk() ? 'product.reviewSent' : 'product.alreadyReviewed') }}</p>
                </aside>
              } @else {
                <form class="panel write" (ngSubmit)="sendReview(p.id)">
                  <h3>{{ i.t('product.writeReview') }}</h3>
                  <fieldset [disabled]="reviewBusy() || !auth.user()" [attr.aria-busy]="reviewBusy()">
                    <label>{{ i.t('product.rating') }}</label>
                    <div class="rate" role="radiogroup" [attr.aria-label]="i.t('product.rating')">
                      @for (s of [1,2,3,4,5]; track s) {
                        <button type="button" role="radio" [attr.aria-checked]="s === rating()" [class.on]="s <= rating()" (click)="rating.set(s)" [attr.aria-label]="s">★</button>
                      }
                    </div>
                    <div class="field">
                      <label for="comment">{{ i.t('product.comment') }}</label>
                      <textarea id="comment" name="comment" rows="3" [(ngModel)]="comment"></textarea>
                    </div>
                    @if (reviewMsg()) { <div class="alert alert-error" role="alert">{{ reviewMsg() }}</div> }
                    <button class="btn btn-primary" type="submit">{{ i.t(reviewBusy() ? 'common.loading' : 'product.sendReview') }}</button>
                  </fieldset>
                </form>
              }
            } @else {
              <aside class="panel write">
                <h3>{{ i.t('product.writeReview') }}</h3>
                <a routerLink="/login" [queryParams]="{ returnUrl: '/product/' + p.id }">{{ i.t('product.loginToReview') }}</a>
              </aside>
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
    .write fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
    .write fieldset:disabled { opacity: .65; }
    .rate { display: flex; gap: 4px; margin-bottom: 1rem; }
    .rate button {
      font-size: 1.7rem; line-height: 1; border: 0; background: none; cursor: pointer; color: #d6e4ea; padding: 0 2px;
    }
    .rate button.on { color: var(--sun); }
    @media (max-width: 860px) {
      .top, .rev-grid { grid-template-columns: 1fr; }
      .art { height: 280px; }
    }
  `],
})
export class ProductComponent {
  readonly i = inject(I18nService);
  readonly money = inject(CurrencyService);
  readonly auth = inject(AuthService);
  readonly cart = inject(CartService);
  private api = inject(ApiService);
  private router = inject(Router);
  private destroyRef = inject(DestroyRef);

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
  readonly reviewBusy = signal(false);
  private readonly duplicateReview = signal<string | null>(null);
  readonly hasReviewed = computed(() => {
    const user = this.auth.user();
    const product = this.product();
    return !!user && !!product && (
      product.reviews.some(review => review.user_id === user.id)
      || this.duplicateReview() === `${product.id}:${user.id}`
    );
  });

  constructor() {
    effect(onCleanup => {
      const id = Number(this.id());
      this.product.set(null);
      this.error.set(false);
      const request = this.load(id);
      onCleanup(() => request.unsubscribe());
    });
    effect(() => {
      this.id();
      this.auth.user()?.id;
      this.comment = '';
      this.rating.set(5);
      this.reviewMsg.set('');
      this.reviewOk.set(false);
      this.duplicateReview.set(null);
    });
  }

  load(id: number) {
    return this.api.product(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: p => { if (Number(this.id()) === id) { this.product.set(p); this.qty.set(1); } },
      error: () => { if (Number(this.id()) === id) this.error.set(true); },
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
    const user = this.auth.user();
    if (!user || this.reviewBusy() || this.hasReviewed() || this.product()?.id !== productId) return;
    this.reviewBusy.set(true);
    this.reviewMsg.set('');
    this.api.addReview(productId, this.rating(), this.comment).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.reviewBusy.set(false)),
    ).subscribe({
      next: review => {
        // Show the saved review immediately, so the form cannot be submitted
        // again while another request is loading updated product information.
        this.product.update(product => {
          if (!product || product.id !== productId) return product;
          const reviews = [...product.reviews.filter(item => item.id !== review.id), review];
          return { ...product, reviews, review_count: reviews.length,
            avg_rating: reviews.reduce((total, item) => total + item.rating, 0) / reviews.length };
        });
        if (Number(this.id()) === productId && this.auth.user()?.id === user.id) {
          this.reviewOk.set(true);
          this.comment = '';
        }
      },
      error: e => {
        if (Number(this.id()) !== productId || this.auth.user()?.id !== user.id) return;
        this.reviewOk.set(false);
        if (e.error?.code === 'review_exists') {
          this.duplicateReview.set(`${productId}:${user.id}`);
          this.load(productId);
        } else {
          this.reviewMsg.set(e.error?.rating?.[0] ?? e.error?.comment?.[0] ?? this.i.t('common.error'));
        }
      },
    });
  }
}
