import { Component, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { CurrencyService } from '../core/currency.service';
import { Product } from '../core/models';
import { ProductImageComponent } from './product-image.component';
import { StarsComponent } from './stars.component';
import { FavoritesService } from '../core/favorites.service';
import { NotifyButtonComponent } from './notify-button.component';


@Component({
  selector: 'app-product-card',
  imports: [RouterLink, ProductImageComponent, StarsComponent, NotifyButtonComponent],
  template: `
    @let p = product();
    <article class="card">
      <a class="photo" [routerLink]="['/product', p.id]" [attr.aria-label]="i.pick(p)">
        <app-product-image [product]="p" />
        @if (p.stock_quantity > 0 && p.stock_quantity < 10) {
          <span class="badge low">{{ i.t('product.left', { n: p.stock_quantity }) }}</span>
        } @else if (rank()) {
          <span class="badge top">#{{ rank() }}</span>
        }
      </a>
      <button type="button" class="like" [class.on]="fav.isLiked(p.id)" (click)="like()"
              [attr.aria-pressed]="fav.isLiked(p.id)"
              [attr.aria-label]="fav.isLiked(p.id) ? i.t('product.unlike') : i.t('product.like')">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 21s-7.5-4.6-9.5-9.2C1 8 3.4 4.5 7 4.5c2 0 3.5 1 5 3 1.5-2 3-3 5-3 3.6 0 6 3.5 4.5 7.3C19.5 16.4 12 21 12 21z"/></svg>
      </button>
      <div class="body">
        <span class="meta">{{ p.brand || i.pick(p.category) }}</span>
        <h3><a [routerLink]="['/product', p.id]">{{ i.pick(p) }}</a></h3>
        <app-stars [value]="p.avg_rating" [count]="p.review_count" />
        <span class="price">{{ money.format(p.price) }}</span>
        @if (p.stock_quantity === 0) {
          <span class="sold">{{ i.t('product.soldOut') }}</span>
          <app-notify-button [productId]="p.id" />
        } @else {
          <button class="add" type="button" (click)="add()" [disabled]="busy()" [class.done]="cart.quantityOf(p.id) > 0">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2.5l2.2 10.5h10.6L20.5 7H6.4"/><circle cx="9.5" cy="19" r="1.4"/><circle cx="17" cy="19" r="1.4"/></svg>
            {{ cart.quantityOf(p.id) > 0 ? i.t('product.added') + ' · ' + cart.quantityOf(p.id) : i.t('product.add') }}
          </button>
        }
      </div>
    </article>
  `,
  styles: [`
    /* the heart button is positioned inside the card, so the card host must be the reference box */
    :host { display: block; position: relative; height: 100%; min-width: 0; }
    .card {
      background: #fff; border: 1px solid var(--line); border-radius: var(--r-md); overflow: hidden;
      display: flex; flex-direction: column; height: 100%; transition: box-shadow .15s, border-color .15s;
      position: relative;
    }
    .card:hover { border-color: #cfd9d5; box-shadow: 0 10px 28px -18px rgba(14, 59, 46, .45); }
    .photo { position: relative; display: block; aspect-ratio: 1 / .9; background: var(--soft); padding: 14px; overflow: hidden; min-height: 0; }
    .badge {
      position: absolute; left: 10px; top: 10px; font-weight: 700; font-size: .72rem;
      padding: .3em .65em; border-radius: 6px;
    }
    .badge.low { background: var(--red); color: #fff; }
    .badge.top { background: var(--amber); color: var(--green-900); }
    .body { padding: .85rem .95rem 1rem; display: flex; flex-direction: column; gap: .3rem; flex: 1; }
    .meta { font-size: .78rem; color: var(--muted); }
    h3 {
      margin: 0; font-size: .95rem; font-weight: 600; line-height: 1.35; min-height: 2.7em;
      display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden;
    }
    h3 a { color: var(--text); }
    .price { font-weight: 700; font-size: 1.15rem; color: var(--green-900); margin-top: .15rem; }
    .add {
      margin-top: auto; display: inline-flex; align-items: center; justify-content: center; gap: .4rem;
      font: 600 .86rem var(--font-body); cursor: pointer; white-space: nowrap;
      border: 1.5px solid var(--green-700); background: #fff; color: var(--green-700);
      padding: .55em .8em; border-radius: var(--r-sm);
    }
    .add:hover { background: var(--green-700); color: #fff; }
    .add.done { background: var(--green-50); border-color: var(--green-50); color: var(--green-700); }
    .add svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .sold { margin-top: auto; color: var(--red); font-weight: 600; font-size: .8rem; padding: .2em 0 .45em; }
    .like {
      position: absolute; right: 10px; top: 10px; z-index: 1; width: 36px; height: 36px; border-radius: 50%;
      border: 0; background: #fff; cursor: pointer; display: grid; place-items: center;
      box-shadow: 0 4px 12px -4px rgba(14, 59, 46, .35);
    }
    .like svg { width: 20px; height: 20px; fill: none; stroke: var(--muted); stroke-width: 2; stroke-linejoin: round; }
    .like:hover svg { stroke: var(--red); }
    .like.on svg { fill: var(--red); stroke: var(--red); }
  `],
})
export class ProductCardComponent {
  readonly product = input.required<Product>();
  /** position in the best-seller list (optional) */
  readonly rank = input<number | null>(null);
  readonly i = inject(I18nService);
  readonly money = inject(CurrencyService);
  readonly cart = inject(CartService);
  private auth = inject(AuthService);
  private router = inject(Router);
  readonly busy = signal(false);
  readonly fav = inject(FavoritesService);

  add() {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.busy.set(true);
    this.cart.add(this.product().id).subscribe({
      next: () => this.busy.set(false),
      error: () => this.busy.set(false),
    });
  }
  like() {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.fav.toggle(this.product().id).subscribe({ error: () => {} });
  }
}
