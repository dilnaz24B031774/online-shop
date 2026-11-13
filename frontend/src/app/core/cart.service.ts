import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { Cart } from './models';

/** Keeps the cart in one place so the header badge and the cart page agree. */
@Injectable({ providedIn: 'root' })
export class CartService {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  readonly cart = signal<Cart | null>(null);
  readonly count = computed(() => this.cart()?.count ?? 0);

  constructor() {
    // reload the cart when the user logs in or out
    effect(() => {
      if (this.auth.isLoggedIn()) this.load().subscribe({ error: () => {} });
      else this.cart.set(null);
    });
  }

  load(): Observable<Cart> {
    return this.api.cart().pipe(tap(c => this.cart.set(c)));
  }

  quantityOf(productId: number): number {
    return this.cart()?.items.find(i => i.product.id === productId)?.quantity ?? 0;
  }

  setQuantity(productId: number, quantity: number): Observable<Cart> {
    return this.api.setCartQuantity(productId, quantity).pipe(tap(c => this.cart.set(c)));
  }

  add(productId: number, quantity = 1): Observable<Cart> {
    return this.setQuantity(productId, this.quantityOf(productId) + quantity);
  }
}
