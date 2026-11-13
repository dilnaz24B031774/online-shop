import { Component, computed, inject, input, signal } from '@angular/core';

import { I18nService } from '../core/i18n.service';
import { ImagesService } from '../core/images.service';
import { Product } from '../core/models';

/** Icons for products without a photo, by category. */
const ICONS: Record<string, string> = {
  Electronics: 'M4 14v-2a8 8 0 0 1 16 0v2M4 14h3v6H5a1 1 0 0 1-1-1zM20 14h-3v6h2a1 1 0 0 0 1-1z',
  Stationery: 'M15 4l5 5L9 20H4v-5zM13 6l5 5',
  Home: 'M8 3h8l3.5 8h-15zM12 11v8M8 21h8',
  Books: 'M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5zM5 19.5V4.5M9 7h6',
  Fashion: 'M8 3l4 2 4-2 4 4-3 3v11H7V10L4 7z',
  Shoes: 'M3 16h18v3H3zM3 16c0-4 2-9 4-9l3 4c2 1 6 2 9 3 1 .4 2 1 2 2',
  Accessories: 'M9 2h6l1 5H8zM9 17h6l-1 5h-4zM12 7a5 5 0 1 1 0 10 5 5 0 0 1 0-10z',
  Beauty: 'M10 3h4v5h-4zM8 8h8v13H8z',
  Sports: 'M12 3a9 9 0 1 1 0 18 9 9 0 0 1 0-18zM3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18',
};
const DEFAULT_ICON = 'M4 7h16l-1.5 12h-13zM9 7a3 3 0 0 1 6 0';

@Component({
  selector: 'app-product-image',
  template: `
    @if (src() && !failed()) {
      <img [src]="src()" [alt]="i.pick(product())" loading="lazy" (error)="failed.set(true)" />
    } @else {
      <span class="placeholder" role="img" [attr.aria-label]="i.pick(product())">
        <svg viewBox="0 0 24 24"><path [attr.d]="icon()"/></svg>
      </span>
    }
  `,
  styles: [`
    :host { display: grid; place-items: center; width: 100%; height: 100%; overflow: hidden; }
    img { width: 100%; height: 100%; object-fit: contain; display: block; }
    .placeholder {
      width: 100%; height: 100%; display: grid; place-items: center;
      background: radial-gradient(circle at 50% 50%, var(--green-50) 0 32%, transparent 33%);
    }
    svg { width: 34%; max-width: 90px; fill: none; stroke: var(--green-700); stroke-width: 1.4;
          stroke-linecap: round; stroke-linejoin: round; }
  `],
})
export class ProductImageComponent {
  readonly product = input.required<Pick<Product, 'sku' | 'image_url' | 'name_en' | 'name_ru' | 'name_kk' | 'category'>>();
  readonly i = inject(I18nService);
  private images = inject(ImagesService);
  readonly failed = signal(false);
  readonly src = computed(() => this.images.src(this.product()));
  readonly icon = computed(() => ICONS[this.product().category?.name_en] ?? DEFAULT_ICON);
}
