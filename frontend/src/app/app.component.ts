import { Component, OnInit, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { filter, map } from 'rxjs';
import { FormsModule } from '@angular/forms';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ApiService } from './core/api.service';
import { RegionService } from './core/region.service';
import { RegionModalComponent } from './shared/region-modal.component';
import { AuthService } from './core/auth.service';
import { CartService } from './core/cart.service';
import { CurrencyService } from './core/currency.service';
import { I18nService, LANGS } from './core/i18n.service';
import { Category } from './core/models';
import { AssistantComponent } from './shared/assistant.component';
import { FavoritesService } from './core/favorites.service';
import { ThemeService } from './core/theme.service';
import { NotificationBellComponent } from './shared/notification-bell.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, FormsModule, AssistantComponent, NotificationBellComponent, RegionModalComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly auth = inject(AuthService);
  readonly region = inject(RegionService);
  readonly cart = inject(CartService);
  readonly theme = inject(ThemeService);   // created here, so the saved theme is applied on start
<<<<<<< HEAD
  readonly money = inject(CurrencyService);
=======
>>>>>>> origin/dilyara-changes
  private api = inject(ApiService);
  private router = inject(Router);
  /** /pay/... is the "bank app" on the phone: no shop header, footer or assistant there */
  readonly payPage = toSignal(this.router.events.pipe(
    filter(e => e instanceof NavigationEnd), map(() => this.router.url.startsWith('/pay/'))),
    { initialValue: location.pathname.startsWith('/pay/') });

  readonly langs = LANGS;
  readonly adminUrl = `${location.protocol}//${location.hostname || '127.0.0.1'}:8000/staff/`;
  readonly categories = signal<Category[]>([]);
  readonly fav = inject(FavoritesService);
  readonly year = new Date().getFullYear();
  query = '';
  searchCategory = '';

  ngOnInit() {
    this.region.load();
    this.api.categories().subscribe({ next: c => this.categories.set(c), error: () => {} });
  }

  search() {
    const q = this.query.trim();
    if (this.searchCategory) {
      // search inside one category -> catalog page with filter
      this.router.navigate(['/catalog'], { queryParams: { category: this.searchCategory, q: q || null } });
    } else if (q) {
      // search everywhere -> products, categories and orders
      this.router.navigate(['/search'], { queryParams: { q } });
    }
  }
}
