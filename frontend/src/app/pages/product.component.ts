import { Component, computed, DestroyRef, effect, inject, input, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { DOCUMENT, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { finalize, Subscription } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { CurrencyService } from '../core/currency.service';
import { ProductDetail } from '../core/models';
import { ProductImageComponent } from '../shared/product-image.component';
import { StarsComponent } from '../shared/stars.component';
import { FavoritesService } from '../core/favorites.service';
import { NotifyButtonComponent } from '../shared/notify-button.component';
import { RegionService } from '../core/region.service';

@Component({
  selector: 'app-product',
  imports: [RouterLink, FormsModule, DatePipe, ProductImageComponent, StarsComponent, NotifyButtonComponent],
  template: `
    <div class="container page">
      <a routerLink="/catalog" class="back">← {{ i.t('product.back') }}</a>

      @if (product(); as p) {
        <div class="top">
          <div class="media">
            <div class="art">
              @if (photo(); as src) {
                <img class="main-photo" [src]="src" [alt]="i.pick(p)" />
              } @else {
                <app-product-image [product]="p" />
              }
            </div>
            @if ((p.images?.length ?? 0) > 1) {
              <div class="thumbs" role="list">
                @for (src of p.images; track src; let n = $index) {
                  <button type="button" role="listitem" class="thumb" [class.on]="(photo() ?? p.images![0]) === src"
                          [attr.aria-label]="i.pick(p) + ' ' + (n + 1)" (click)="photo.set(src)">
                    <img [src]="src" alt="" loading="lazy" />
                  </button>
                }
              </div>
            }
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
              @if (p.stock_quantity === 0) {
                <app-notify-button [productId]="p.id" size="big" />
              }
              @if (cartError()) { <div class="alert alert-error">{{ cartError() }}</div> }
              <button type="button" class="delivery" (click)="region.ask()">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 7h11v9H3zM14 10h4l3 3v3h-7M7 19a2 2 0 1 0 0-.1M17 19a2 2 0 1 0 0-.1"/></svg>
                @if (region.current(); as c) {
                  <span>{{ i.t('region.delivery', { city: i.pick(c), min: c.delivery_days_min, max: c.delivery_days_max }) }}</span>
                } @else {
                  <span>{{ i.t('region.deliveryPick') }}</span>
                }
                <span class="change">{{ i.t('region.change') }}</span>
              </button>
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
                  @if (r.photos?.length) {
                    <div class="rev-photos">
                      @for (src of r.photos; track src) {
                        <button type="button" (click)="viewer.set(src)" [attr.aria-label]="i.t('review.openPhoto')">
                          <img [src]="src" alt="" loading="lazy" />
                        </button>
                      }
                    </div>
                  }
                  <small class="muted">{{ r.created_at | date: 'mediumDate' }}</small>
                </article>
              } @empty {
                <p class="muted">{{ i.t('product.noReviews') }}</p>
              }
            </div>

            @if (auth.isLoggedIn()) {
              @if (eligibilityLoading() || !auth.user()) {
                <aside class="panel write">
                  <h3>{{ i.t('product.writeReview') }}</h3>
                  <p class="muted" role="status">{{ i.t('common.loading') }}</p>
                </aside>
              } @else if (eligibilityError()) {
                <aside class="panel write">
                  <h3>{{ i.t('product.writeReview') }}</h3>
                  <p class="muted" role="alert">{{ i.t('product.reviewEligibilityError') }}</p>
                  <button class="btn btn-outline" type="button" (click)="refreshProduct()">{{ i.t('settings.retry') }}</button>
                </aside>
              } @else if (eligibility()?.can_review) {
                <form class="panel write" (ngSubmit)="sendReview(p.id)">
                  <h3>{{ i.t('product.writeReview') }}</h3>
                  @if (reviewOk()) { <p class="alert alert-ok" role="status">{{ i.t('product.reviewSent') }}</p> }
                  <p class="muted review-rule">{{ i.t('product.reviewPerPurchase') }}</p>
                  <fieldset [disabled]="reviewBusy()" [attr.aria-busy]="reviewBusy()">
                    @if (eligibility(); as available) {
                      @if (available.purchases.length > 1) {
                        <div class="field">
                          <label for="review-purchase">{{ i.t('product.reviewPurchase') }}</label>
                          <select id="review-purchase" name="order_item_id" [ngModel]="selectedPurchase()" (ngModelChange)="choosePurchase($event)">
                            @for (purchase of available.purchases; track purchase.order_item_id) {
                              <option [ngValue]="purchase.order_item_id">{{ i.t('product.reviewOrder', { n: purchase.order_id }) }} · {{ purchase.purchased_at | date: 'mediumDate' }}</option>
                            }
                          </select>
                        </div>
                      } @else {
                        @for (purchase of available.purchases; track purchase.order_item_id) {
                          <p class="purchase-caption">{{ i.t('product.reviewOrder', { n: purchase.order_id }) }} · {{ purchase.purchased_at | date: 'mediumDate' }}</p>
                        }
                      }
                    }
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
                    <div class="field">
                      <label>{{ i.t('review.photos') }}</label>
                      <div class="pick">
                        @for (ph of picked(); track ph.url; let n = $index) {
                          <div class="pick-item">
                            <img [src]="ph.url" alt="" />
                            <button type="button" class="pick-x" (click)="removePhoto(n)" [attr.aria-label]="i.t('review.remove')">×</button>
                          </div>
                        }
                        @if (picked().length < 3) {
                          <label class="pick-add">
                            <input type="file" accept="image/jpeg,image/png,image/webp" multiple (change)="addPhotos($event)" />
                            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h3l2-3h6l2 3h3v13H4zM12 10a3.5 3.5 0 1 0 0 7 3.5 3.5 0 0 0 0-7z"/></svg>
                            <span>{{ i.t('review.add') }}</span>
                          </label>
                        }
                      </div>
                      <small class="muted">{{ i.t('review.rules') }}</small>
                    </div>
                    @if (reviewMsg()) { <div class="alert alert-error" role="alert">{{ reviewMsg() }}</div> }
                    <button class="btn btn-primary" type="submit" [disabled]="!canReview()">{{ i.t(reviewBusy() ? 'common.loading' : 'product.sendReview') }}</button>
                  </fieldset>
                </form>
              } @else {
                <aside class="panel write">
                  <h3>{{ i.t('product.writeReview') }}</h3>
                  @if (reviewOk()) { <p class="alert alert-ok" role="status">{{ i.t('product.reviewSent') }}</p> }
                  <p class="muted" role="status">{{ i.t(eligibility()?.reason === 'review_exists' ? 'product.alreadyReviewed' : 'product.purchaseRequired') }}</p>
                  <a routerLink="/orders">{{ i.t('orders.title') }}</a>
                </aside>
              }
            } @else {
              <aside class="panel write">
                <h3>{{ i.t('product.writeReview') }}</h3>
                <p class="muted">{{ i.t('product.purchaseRequired') }}</p>
                <a routerLink="/login" [queryParams]="{ returnUrl: '/product/' + p.id }">{{ i.t('product.loginToReview') }}</a>
              </aside>
            }
          </div>
        </section>
        @if (viewer(); as v) {
          <div class="viewer" role="dialog" aria-modal="true" (click)="viewer.set(null)">
            <img [src]="v" alt="" />
            <button type="button" class="viewer-x" [attr.aria-label]="i.t('common.close')">×</button>
          </div>
        }
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
    .delivery { margin-top: .9rem; width: 100%; display: flex; align-items: center; gap: .55rem; flex-wrap: wrap; text-align: left;
                border: 0; border-top: 1px solid var(--line); background: none; padding: .85rem 0 0; color: var(--text); font: 500 .88rem var(--font-body); cursor: pointer; }
    .delivery svg { width: 20px; height: 20px; flex: none; fill: none; stroke: var(--green-700); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .delivery .change { margin-left: auto; color: var(--green-700); font-weight: 600; font-size: .82rem; }
    .delivery:hover .change { text-decoration: underline; }
    .media { min-width: 0; }
    .art { border-radius: 18px; overflow: hidden; height: 460px; background: var(--soft); padding: 2rem; border: 1px solid var(--line); }
    .main-photo { width: 100%; height: 100%; object-fit: contain; display: block; }
    .thumbs { display: flex; gap: 10px; margin-top: 12px; overflow-x: auto; padding-bottom: 2px; }
    .thumb { flex: none; width: 74px; height: 74px; padding: 6px; border-radius: 12px; cursor: pointer;
             background: var(--soft); border: 2px solid transparent; transition: border-color .15s; }
    .thumb:hover { border-color: var(--line); }
    .thumb.on { border-color: var(--green-700); }
    .thumb img { width: 100%; height: 100%; object-fit: contain; display: block; }

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
    .rev-photos { display: flex; gap: 8px; margin: .2rem 0 .5rem; }
    .rev-photos button { width: 76px; height: 76px; padding: 0; border: 1px solid var(--line); border-radius: 10px; overflow: hidden; cursor: zoom-in; background: var(--soft); }
    .rev-photos img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .pick { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: .3rem; }
    .pick-item { position: relative; width: 72px; height: 72px; border-radius: 10px; overflow: hidden; border: 1px solid var(--line); }
    .pick-item img { width: 100%; height: 100%; object-fit: cover; display: block; }
    .pick-x { position: absolute; top: 3px; right: 3px; width: 22px; height: 22px; border-radius: 50%; border: 0; cursor: pointer;
              background: rgba(0, 0, 0, .6); color: #fff; font-size: 15px; line-height: 22px; padding: 0; }
    .pick-add { width: 72px; height: 72px; border: 1.5px dashed var(--line); border-radius: 10px; display: grid; place-content: center; justify-items: center;
                gap: 2px; cursor: pointer; color: var(--muted); font-size: .7rem; font-weight: 600; text-align: center; }
    .pick-add:hover { border-color: var(--green-700); color: var(--green-700); }
    .pick-add input { position: absolute; width: 1px; height: 1px; opacity: 0; pointer-events: none; }
    .pick-add svg { width: 22px; height: 22px; fill: none; stroke: currentColor; stroke-width: 1.7; stroke-linejoin: round; }
    .viewer { position: fixed; inset: 0; z-index: 950; background: rgba(5, 15, 12, .85); display: grid; place-items: center; padding: 24px; cursor: zoom-out; }
    .viewer img { max-width: 100%; max-height: 100%; border-radius: 12px; }
    .viewer-x { position: absolute; top: 14px; right: 18px; border: 0; background: none; color: #fff; font-size: 2rem; cursor: pointer; }
    .who { font-weight: 700; }
    .write h3 { margin-bottom: 1rem; }
    .write fieldset { border: 0; padding: 0; margin: 0; min-width: 0; }
    .write fieldset:disabled { opacity: .65; }
    .review-rule { font-size: .88rem; line-height: 1.5; }
    .purchase-caption { margin-bottom: 1rem; font-weight: 600; font-size: .9rem; }
    .write .alert { margin: 0 0 1rem; }
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
  readonly money = inject(CurrencyService);
  readonly auth = inject(AuthService);
  readonly cart = inject(CartService);
  readonly region = inject(RegionService);
  private api = inject(ApiService);
  private router = inject(Router);
  private doc = inject(DOCUMENT);
  private destroyRef = inject(DestroyRef);

  readonly id = input.required<string>();   // from /product/:id

  readonly product = signal<ProductDetail | null>(null);
  readonly photo = signal<string | null>(null);   // photo picked in the gallery
  readonly error = signal(false);
  readonly qty = signal(1);
  readonly busy = signal(false);
  readonly cartError = signal('');

  readonly rating = signal(5);
  comment = '';
  readonly reviewMsg = signal('');
  readonly reviewOk = signal(false);
  readonly picked = signal<{ file: File; url: string }[]>([]);   // photos chosen for the review
  readonly viewer = signal<string | null>(null);                  // photo opened full size
  readonly fav = inject(FavoritesService);
  readonly reviewBusy = signal(false);
  readonly eligibilityLoading = signal(false);
  readonly eligibilityError = signal(false);
  readonly selectedPurchase = signal<number | null>(null);
  readonly eligibility = computed(() => this.product()?.review_eligibility ?? null);
  readonly canReview = computed(() => !!this.auth.user() && !!this.eligibility()?.can_review
    && !this.eligibilityLoading() && !this.eligibilityError() && !this.reviewBusy()
    && this.selectedPurchase() !== null);
  private readonly accountId = computed(() => this.auth.user()?.id ?? null);
  private readonly context = computed(() => `${this.id()}:${this.auth.isLoggedIn() ? this.accountId() ?? 'restoring' : 'guest'}`);
  private productRequest?: Subscription;
  private reviewRequest?: Subscription;

  constructor() {
    effect(onCleanup => {
      const context = this.context();
      untracked(() => {
        this.product.set(null);
        this.error.set(false);
        this.comment = '';
        this.rating.set(5);
        this.reviewMsg.set('');
        this.reviewOk.set(false);
        this.selectedPurchase.set(null);
        this.load(context, true);
      });
      onCleanup(() => {
        this.productRequest?.unsubscribe();
        this.reviewRequest?.unsubscribe();
      });
    });
  }

  refreshProduct() {
    this.load(this.context());
  }

  choosePurchase(orderItemId: number) {
    this.selectedPurchase.set(orderItemId);
    this.reviewMsg.set('');
  }

  private load(context: string, resetQuantity = false) {
    this.productRequest?.unsubscribe();
    this.eligibilityLoading.set(true);
    this.eligibilityError.set(false);
    this.productRequest = this.api.product(Number(this.id())).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => { if (this.context() === context) this.eligibilityLoading.set(false); }),
    ).subscribe({
      next: p => {
        if (this.context() !== context) return;
        this.product.set(p);
        if (resetQuantity) { this.qty.set(1); this.photo.set(null); }
        const purchases = p.review_eligibility?.purchases ?? [];
        if (!purchases.some(purchase => purchase.order_item_id === this.selectedPurchase())) {
          this.selectedPurchase.set(purchases[0]?.order_item_id ?? null);
        }
      },
      error: () => {
        if (this.context() !== context) return;
        this.eligibilityError.set(true);
        if (!this.product()) this.error.set(true);
      },
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

  addPhotos(event: Event) {
    const input = event.target as HTMLInputElement;
    const ok = ['image/jpeg', 'image/png', 'image/webp'];
    const room = 3 - this.picked().length;
    const files = Array.from(input.files ?? []);
    input.value = '';
    const bad = files.find(f => !ok.includes(f.type) || f.size > 5 * 1024 * 1024);
    if (bad || files.length > room) {
      this.reviewOk.set(false);
      this.reviewMsg.set(this.i.t('review.rules'));
    }
    const good = files.filter(f => ok.includes(f.type) && f.size <= 5 * 1024 * 1024).slice(0, room);
    this.picked.update(list => [...list, ...good.map(file => ({ file, url: URL.createObjectURL(file) }))]);
  }

  removePhoto(index: number) {
    const item = this.picked()[index];
    if (item) URL.revokeObjectURL(item.url);
    this.picked.update(list => list.filter((_, n) => n !== index));
  }

  sendReview(productId: number) {
    const orderItemId = this.selectedPurchase();
    const context = this.context();
    if (!this.canReview() || orderItemId === null || this.product()?.id !== productId
      || !this.eligibility()?.purchases.some(purchase => purchase.order_item_id === orderItemId)) return;
    this.reviewBusy.set(true);
    this.reviewMsg.set('');
    this.reviewOk.set(false);
    this.reviewRequest = this.api.addReview(productId, this.rating(), this.comment, this.picked().map(p => p.file), orderItemId).pipe(
      takeUntilDestroyed(this.destroyRef),
      finalize(() => this.reviewBusy.set(false)),
    ).subscribe({
      next: review => {
        if (this.context() !== context) return;
        // Consume this purchase immediately while refreshing the authoritative
        // eligibility, so an additional purchase can still receive a review.
        this.product.update(product => {
          if (!product || product.id !== productId) return product;
          const reviews = [...product.reviews.filter(item => item.id !== review.id), review];
          const purchases = product.review_eligibility.purchases.filter(purchase => purchase.order_item_id !== orderItemId);
          return { ...product, reviews, review_count: reviews.length,
            avg_rating: reviews.reduce((total, item) => total + item.rating, 0) / reviews.length,
            review_eligibility: { can_review: purchases.length > 0, remaining_purchases: purchases.length,
              reason: purchases.length ? null : 'review_exists', purchases } };
        });
        this.reviewOk.set(true);
        this.comment = '';
        this.picked().forEach(p => URL.revokeObjectURL(p.url));
        this.picked.set([]);
        this.rating.set(5);
        this.load(context);
      },
      error: e => {
        if (this.context() !== context) return;
        this.reviewOk.set(false);
        if (e.status === 401) {
          this.auth.logout(false);
          this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
        } else if (e.error?.code === 'review_exists' || e.error?.code === 'purchase_required') {
          this.reviewMsg.set(this.i.t(e.error.code === 'review_exists' ? 'product.reviewPurchaseUsed' : 'product.purchaseRequired'));
          this.load(context);
        } else {
          this.reviewMsg.set(e.error?.rating?.[0] ?? e.error?.comment?.[0] ?? e.error?.photos?.[0] ?? this.i.t('common.error'));
        }
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
