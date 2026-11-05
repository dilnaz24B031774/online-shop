import { Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';

import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { ProductImageComponent } from '../shared/product-image.component';

@Component({
  selector: 'app-cart',
  imports: [RouterLink, ProductImageComponent],
  template: `
    <div class="container page">
      <h1>{{ i.t('cart.title') }}</h1>

      @if (error()) { <div class="alert alert-error">{{ error() }}</div> }

      @if (cart.cart(); as c) {
        @if (c.items.length === 0) {
          <div class="panel empty">
            <p>{{ i.t('cart.empty') }}</p>
            <a routerLink="/catalog" class="btn btn-primary">{{ i.t('hero.shop') }}</a>
          </div>
        } @else {
          <div class="layout">
            <div class="items">
              @for (item of c.items; track item.id) {
                <article class="row panel">
                  <a class="thumb" [routerLink]="['/product', item.product.id]">
                    <app-product-image [product]="item.product" />
                  </a>
                  <div class="name">
                    <a [routerLink]="['/product', item.product.id]"><strong>{{ i.pick(item.product) }}</strong></a>
                    <span class="muted">\${{ item.product.price }} · {{ i.pick(item.product.category) }}</span>
                    <button type="button" class="remove" (click)="setQty(item.product.id, 0)">{{ i.t('cart.remove') }}</button>
                  </div>
                  <div class="stepper">
                    <button type="button" (click)="setQty(item.product.id, item.quantity - 1)" aria-label="−">−</button>
                    <span>{{ item.quantity }}</span>
                    <button type="button" (click)="setQty(item.product.id, item.quantity + 1)"
                            [disabled]="item.quantity >= item.product.stock_quantity" aria-label="+">+</button>
                  </div>
                  <strong class="line">\${{ item.line_total }}</strong>
                </article>
              }
            </div>

            <aside class="summary panel">
              <div class="sum-row"><span>{{ c.count }} {{ i.t('cart.items') }}</span></div>
              <div class="sum-row total"><span>{{ i.t('cart.total') }}</span><strong>\${{ c.total }}</strong></div>
              <a routerLink="/checkout" class="btn btn-sun btn-block">{{ i.t('cart.checkout') }}</a>
            </aside>
          </div>
        }
      } @else {
        <p class="muted">{{ i.t('common.loading') }}</p>
      }
    </div>
  `,
  styles: [`
    .layout { display: grid; grid-template-columns: 1fr 320px; gap: 1.6rem; align-items: start; }
    .items { display: flex; flex-direction: column; gap: .9rem; }
    .row { display: grid; grid-template-columns: 96px 1fr auto 90px; gap: 1.1rem; align-items: center; padding: .9rem; }
    .thumb { display: block; height: 84px; border-radius: 10px; overflow: hidden; background: var(--soft); padding: 6px; }
    
    .name { display: flex; flex-direction: column; gap: .15rem; }
    .name a { color: var(--ink); }
    .remove { align-self: flex-start; border: 0; background: none; padding: 0; color: var(--berry); font: 600 .85rem var(--font-body); cursor: pointer; margin-top: .2rem; }
    .stepper { display: flex; align-items: center; background: var(--sky); border-radius: 999px; }
    .stepper button { width: 38px; height: 38px; border: 0; background: transparent; font-size: 1.2rem; cursor: pointer; color: var(--ink); }
    .stepper button:disabled { opacity: .35; cursor: default; }
    .stepper span { min-width: 24px; text-align: center; font-weight: 700; }
    .line { text-align: right; font-family: var(--font-display); }
    .summary { position: sticky; top: 180px; }
    .sum-row { display: flex; justify-content: space-between; margin-bottom: .8rem; color: var(--ink-soft); }
    .total { color: var(--ink); font-size: 1.2rem; border-top: 2px dashed var(--line); padding-top: .8rem; }
    .total strong { font-family: var(--font-display); font-size: 1.6rem; }
    .empty { text-align: center; }
    @media (max-width: 820px) {
      .layout { grid-template-columns: 1fr; }
      .row { grid-template-columns: 72px 1fr; }
      .stepper { grid-column: 2; justify-self: start; }
      .line { grid-column: 2; text-align: left; }
    }
  `],
})
export class CartComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly cart = inject(CartService);
  readonly error = signal('');

  ngOnInit() {
    this.cart.load().subscribe({ error: () => this.error.set(this.i.t('common.error')) });
  }

  setQty(productId: number, qty: number) {
    this.error.set('');
    this.cart.setQuantity(productId, qty).subscribe({
      error: e => this.error.set(e.error?.detail ?? this.i.t('common.error')),
    });
  }
}
