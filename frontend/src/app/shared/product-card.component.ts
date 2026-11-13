import { Component, inject, input, signal } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { Product } from '../core/models';
import { ProductImageComponent } from './product-image.component';
import { StarsComponent } from './stars.component';

@Component({
  selector: 'app-product-card',
  imports: [RouterLink, ProductImageComponent, StarsComponent],
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
      <div class="body">
        <span class="meta">{{ p.brand || i.pick(p.category) }}</span>
        <h3><a [routerLink]="['/product', p.id]">{{ i.pick(p) }}</a></h3>
        <app-stars [value]="p.avg_rating" [count]="p.review_count" />
        <span class="price">\${{ p.price }}</span>
        @if (p.stock_quantity === 0) {
          <span class="sold">{{ i.t('product.soldOut') }}</span>
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
    .card {
      background: #fff; border: 1px solid var(--line); border-radius: var(--r-md); overflow: hidden;
      display: flex; flex-direction: column; height: 100%; transition: box-shadow .15s, border-color .15s;
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
    .sold { margin-top: auto; color: var(--muted); font-weight: 600; font-size: .86rem; padding: .55em 0; }
  `],
})
export class ProductCardComponent {
  readonly product = input.required<Product>();
  /** position in the best-seller list (optional) */
  readonly rank = input<number | null>(null);
  readonly i = inject(I18nService);
  readonly cart = inject(CartService);
  private auth = inject(AuthService);
  private router = inject(Router);
  readonly busy = signal(false);

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
}
