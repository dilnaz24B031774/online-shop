import { Component, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Order } from '../core/models';

@Component({
  selector: 'app-orders',
  imports: [RouterLink, DatePipe],
  template: `
    <div class="container page">
      <h1>{{ i.t('orders.title') }}</h1>
      @if (message()) { <div class="alert alert-ok">{{ message() }}</div> }
      @if (failMsg()) { <div class="alert alert-error">{{ failMsg() }}</div> }

      @if (orders(); as list) {
        @for (o of list; track o.id) {
          <article class="order panel">
            <header>
              <div>
                <h2>{{ i.t('orders.order') }} #{{ o.id }}</h2>
                <span class="muted">{{ o.created_at | date: 'medium' }} · {{ o.shipping_address }}</span>
              </div>
              <span class="status" [class]="'status s-' + o.status">{{ i.t('status.' + o.status) }}</span>
            </header>

            <ol class="track" [attr.aria-label]="i.t('status.' + o.status)">
              @for (s of steps; track s; let idx = $index) {
                <li [class.done]="stepIndex(o) >= idx" [class.cancelled]="o.status === 'cancelled'">{{ i.t('status.' + s) }}</li>
              }
            </ol>

            <ul class="items">
              @for (it of o.items; track it.id) {
                <li>
                  <a [routerLink]="['/product', it.product.id]">{{ i.pick(it.product) }}</a>
                  <span class="muted">× {{ it.quantity }} · \${{ it.unit_price }}</span>
                  <span>\${{ it.line_total }}</span>
                </li>
              }
            </ul>

            <footer>
              <span class="muted">{{ i.t('orders.payment') }}: {{ o.payment_method ? i.t('pay.' + o.payment_method) : '–' }}
                @if (o.payment_status) { ({{ i.t('status.' + o.payment_status) }}) }</span>
              <strong class="sum">\${{ o.total_amount }}</strong>
            </footer>

            @if (o.status === 'paid' || o.status === 'pending') {
              @if (confirmId() === o.id) {
                <div class="confirm" role="alert">
                  <p>{{ i.t('orders.cancelAsk', { n: o.id, sum: o.total_amount }) }}</p>
                  <div class="confirm-actions">
                    <button type="button" class="btn danger" (click)="cancel(o)" [disabled]="busy()">{{ i.t('orders.cancelYes') }}</button>
                    <button type="button" class="btn btn-ghost" (click)="confirmId.set(null)">{{ i.t('orders.cancelNo') }}</button>
                  </div>
                </div>
              } @else {
                <div class="cancel-row">
                  <span class="muted small">{{ i.t('orders.cancelHint') }}</span>
                  <button type="button" class="link-btn" (click)="confirmId.set(o.id)">{{ i.t('orders.cancel') }}</button>
                </div>
              }
            }
          </article>
        } @empty {
          <div class="panel empty">
            <p>{{ i.t('orders.empty') }}</p>
            <a routerLink="/catalog" class="btn btn-primary">{{ i.t('hero.shop') }}</a>
          </div>
        }
      } @else if (error()) {
        <div class="alert alert-error">{{ i.t('common.error') }}</div>
      } @else {
        <p class="muted">{{ i.t('common.loading') }}</p>
      }
    </div>
  `,
  styles: [`
    .order { margin-bottom: 1.2rem; }
    header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
    h2 { font-size: 1.25rem; margin-bottom: .2rem; }
    .status { font-weight: 700; font-size: .85rem; padding: .35em .9em; border-radius: 999px; white-space: nowrap; }
    .s-pending { background: #fdf0d5; color: var(--warn); }
    .s-paid { background: #dff1f3; color: var(--teal-dark); }
    .s-shipped { background: #e4e7f7; color: var(--indigo); }
    .s-delivered { background: #e3f4ea; color: var(--ok); }
    .s-cancelled { background: #fbe9ec; color: var(--berry); }

    .track { list-style: none; padding: 0; margin: 1.2rem 0; display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
    .track li {
      font-size: .82rem; font-weight: 600; color: var(--ink-soft);
      padding-top: .55rem; border-top: 5px solid var(--line);
    }
    .track li.done { border-top-color: var(--teal); color: var(--ink); }
    .track li.cancelled { border-top-color: #f0c7d3; color: var(--ink-soft); }

    .items { list-style: none; padding: 0; margin: 0; border-top: 1px solid var(--line); }
    .items li { display: grid; grid-template-columns: 1fr auto 90px; gap: 1rem; padding: .6rem 0; border-bottom: 1px solid var(--line); }
    .items li span:last-child { text-align: right; font-weight: 600; }
    footer { display: flex; justify-content: space-between; align-items: center; margin-top: 1rem; gap: 1rem; flex-wrap: wrap; }
    .sum { font-family: var(--font-display); font-size: 1.4rem; }
    .empty { text-align: center; }
    .cancel-row { display: flex; justify-content: space-between; align-items: center; gap: 1rem; margin-top: 1rem; padding-top: 1rem; border-top: 1px dashed var(--line); flex-wrap: wrap; }
    .small { font-size: .85rem; }
    .link-btn { border: 1.5px solid var(--line); background: #fff; color: var(--red); font: 600 .88rem var(--font-body); padding: .5em 1em; border-radius: var(--r-sm); cursor: pointer; }
    .link-btn:hover { border-color: var(--red); }
    .confirm { margin-top: 1rem; padding: 1rem 1.1rem; border-radius: var(--r-md); background: #fdecea; }
    .confirm p { margin: 0 0 .8rem; font-weight: 500; color: #8f2a22; }
    .confirm-actions { display: flex; gap: .6rem; flex-wrap: wrap; }
    .btn.danger { background: var(--red); color: #fff; }
    .btn.danger:hover { background: #b93a2f; }
  `],
})
export class OrdersComponent implements OnInit {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  readonly orders = signal<Order[] | null>(null);
  readonly error = signal(false);
  readonly confirmId = signal<number | null>(null);
  readonly busy = signal(false);
  readonly message = signal('');
  readonly failMsg = signal('');
  readonly steps = ['paid', 'shipped', 'delivered'];

  ngOnInit() {
    this.api.orders().subscribe({ next: o => this.orders.set(o), error: () => this.error.set(true) });
  }

  cancel(o: Order) {
    this.busy.set(true);
    this.failMsg.set('');
    this.api.cancelOrder(o.id).subscribe({
      next: updated => {
        this.orders.update(list => (list ?? []).map(x => (x.id === updated.id ? updated : x)));
        this.message.set(this.i.t('orders.cancelled', { n: updated.id, sum: updated.total_amount }));
        this.confirmId.set(null);
        this.busy.set(false);
      },
      error: e => {
        this.failMsg.set(e.error?.detail ?? this.i.t('common.error'));
        this.busy.set(false);
      },
    });
  }

  stepIndex(o: Order): number {
    return this.steps.indexOf(o.status);
  }
}
