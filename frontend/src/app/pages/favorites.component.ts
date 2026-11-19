import { Component, OnInit, inject } from '@angular/core';
import { RouterLink } from '@angular/router';

import { FavoritesService } from '../core/favorites.service';
import { I18nService } from '../core/i18n.service';
import { ProductCardComponent } from '../shared/product-card.component';

/** Separate "Favorites" page (opened from the heart in the header). */
@Component({
  selector: 'app-favorites',
  imports: [RouterLink, ProductCardComponent],
  template: `
    <div class="container page">
      <h2>{{ i.t('profile.favorites') }} <small>{{ fav.count() }}</small></h2>
      @if (fav.items().length) {
        <div class="grid">
          @for (p of fav.items(); track p.id) { <app-product-card [product]="p" /> }
        </div>
      } @else {
        <div class="panel empty">
          <p>{{ i.t('profile.noFavorites') }}</p>
          <a routerLink="/catalog" class="btn btn-primary">{{ i.t('hero.shop') }}</a>
        </div>
      }
    </div>
  `,
  styles: [`
    h2 small { font-family: var(--font-body); font-size: .9rem; color: var(--ink-soft); font-weight: 600; }
    .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: 16px; }
    .empty { text-align: center; }
  `],
})
export class FavoritesComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly fav = inject(FavoritesService);

  ngOnInit() {
    this.fav.load().subscribe({ error: () => {} });
  }
}
