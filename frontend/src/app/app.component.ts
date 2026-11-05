import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';

import { ApiService } from './core/api.service';
import { AuthService } from './core/auth.service';
import { CartService } from './core/cart.service';
import { I18nService, LANGS } from './core/i18n.service';
import { Category } from './core/models';
import { AssistantComponent } from './shared/assistant.component';

@Component({
  selector: 'app-root',
  imports: [RouterOutlet, RouterLink, RouterLinkActive, FormsModule, AssistantComponent],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly auth = inject(AuthService);
  readonly cart = inject(CartService);
  private api = inject(ApiService);
  private router = inject(Router);

  readonly langs = LANGS;
  readonly adminUrl = 'http://127.0.0.1:8000/admin/';
  readonly categories = signal<Category[]>([]);
  readonly year = new Date().getFullYear();
  query = '';
  searchCategory = '';

  ngOnInit() {
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
