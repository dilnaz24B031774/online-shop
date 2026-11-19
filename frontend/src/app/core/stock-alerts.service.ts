import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';

/** Products the customer waits for ("tell me when it is back"), shared by cards and the product page. */
@Injectable({ providedIn: 'root' })
export class StockAlertsService {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  private readonly ids = signal<Set<number>>(new Set());
  readonly count = computed(() => this.ids().size);

  constructor() {
    effect(() => {
      if (this.auth.isLoggedIn()) {
        this.api.stockAlerts().subscribe({ next: r => this.ids.set(new Set(r.product_ids)), error: () => {} });
      } else {
        this.ids.set(new Set());
      }
    });
  }

  isWaiting(productId: number): boolean {
    return this.ids().has(productId);
  }

  toggle(productId: number): Observable<unknown> {
    const waiting = this.isWaiting(productId);
    const request = waiting ? this.api.cancelNotifyMe(productId) : this.api.notifyMe(productId);
    return request.pipe(tap(() => {
      const next = new Set(this.ids());
      if (waiting) next.delete(productId); else next.add(productId);
      this.ids.set(next);
    }));
  }
}
