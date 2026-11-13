import { HttpClient } from '@angular/common/http';
import { Injectable, inject, signal } from '@angular/core';

import { Product } from './models';

/**
 * Product photos.
 * Online: the photo comes from product.image_url (saved in the database).
 * Offline: run  npm run download-images  once — photos are saved in
 * public/products/ and listed in public/products/manifest.json, then they load from the app itself.
 */
@Injectable({ providedIn: 'root' })
export class ImagesService {
  private http = inject(HttpClient);
  private readonly local = signal<Record<string, string>>({});

  constructor() {
    this.http.get<Record<string, string>>('products/manifest.json').subscribe({
      next: files => this.local.set(files),
      error: () => { /* no local photos yet — use the internet links */ },
    });
  }

  src(p: Pick<Product, 'sku' | 'image_url'>): string | null {
    const file = this.local()[p.sku];
    if (file) return `products/${file}`;
    return p.image_url || null;
  }
}
