import { Injectable, computed, effect, inject, signal } from '@angular/core';
import { Observable, tap } from 'rxjs';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { Product } from './models';

/** Keeps liked products in one place so hearts, the header badge and the profile agree. */
@Injectable({ providedIn: 'root' })
export class FavoritesService {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  readonly items = signal<Product[]>([]);
  readonly count = computed(() => this.items().length);
  private readonly ids = computed(() => new Set(this.items().map(p => p.id)));

  constructor() {
    // reload when the user logs in, clear when logs out
    effect(() => {
      if (this.auth.isLoggedIn()) this.load().subscribe({ error: () => {} });
      else this.items.set([]);
    });
  }

  load(): Observable<Product[]> {
    return this.api.favorites().pipe(tap(list => this.items.set(list)));
  }

  isLiked(productId: number): boolean {
    return this.ids().has(productId);
  }

  toggle(productId: number): Observable<Product[]> {
    const request = this.isLiked(productId)
      ? this.api.removeFavorite(productId)
      : this.api.addFavorite(productId);
    return request.pipe(tap(list => this.items.set(list)));
  }
}