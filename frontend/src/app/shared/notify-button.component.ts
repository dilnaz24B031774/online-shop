import { Component, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';

import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { StockAlertsService } from '../core/stock-alerts.service';

/** "Notify me when it is back" for a sold-out product. Compact on cards, full-width on the product page. */
@Component({
  selector: 'app-notify-button',
  template: `
    @let on = alerts.isWaiting(productId());
    <button type="button" class="notify" [class.on]="on" [class.big]="size() === 'big'" (click)="toggle()"
            [disabled]="busy()" [attr.aria-pressed]="on">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        @if (on) { <path d="M5 12.5l4.5 4.5L19 7.5"/> }
        @else { <path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0"/> }
      </svg>
      <span>{{ on ? i.t('stock.waiting') : i.t('stock.notify') }}</span>
    </button>
    @if (size() === 'big') {
      <p class="hint">{{ on ? i.t('stock.waitingHint') : i.t('stock.notifyHint') }}</p>
    }
  `,
  styles: [`
    :host { display: block; margin-top: auto; }
    .notify {
      width: 100%; display: inline-flex; align-items: center; justify-content: center; gap: .45rem;
      border: 1.5px solid var(--green-700); background: #fff; color: var(--green-700); cursor: pointer;
      font: 600 .84rem var(--font-body); padding: .55em .8em; border-radius: 10px; transition: background .15s, color .15s;
    }
    .notify:hover:not(:disabled) { background: var(--green-50); }
    .notify.on { background: var(--green-50); border-color: var(--green-50); color: var(--green-900); }
    .notify.on:hover:not(:disabled) { border-color: var(--green-700); }
    .notify svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; flex: none; }
    .notify.big { font-size: .95rem; padding: .8em 1.1em; border-radius: 12px; }
    .notify.big:not(.on) { background: var(--green-700); color: #fff; }
    .notify.big:not(.on):hover:not(:disabled) { background: var(--green-900); }
    .hint { margin: .55rem 0 0; color: var(--muted); font-size: .84rem; }
  `],
})
export class NotifyButtonComponent {
  readonly i = inject(I18nService);
  readonly alerts = inject(StockAlertsService);
  private auth = inject(AuthService);
  private router = inject(Router);

  readonly productId = input.required<number>();
  readonly size = input<'small' | 'big'>('small');
  readonly busy = signal(false);

  toggle() {
    if (!this.auth.isLoggedIn()) {
      this.router.navigate(['/login'], { queryParams: { returnUrl: this.router.url } });
      return;
    }
    this.busy.set(true);
    this.alerts.toggle(this.productId()).subscribe({
      next: () => this.busy.set(false),
      error: () => this.busy.set(false),
    });
  }
}
