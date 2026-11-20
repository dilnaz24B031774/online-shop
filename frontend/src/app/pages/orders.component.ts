import { Component, OnDestroy, OnInit, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Order } from '../core/models';
import { CountdownComponent } from '../shared/countdown.component';
import { PayLinkService } from '../core/pay-link.service';

/**
 * The list of the user's orders.
 * It is no longer a separate page: it is shown inside the profile (tab "My orders"),
 * see profile.component.ts  ->  <app-orders />
 */
@Component({
  selector: 'app-orders',
  imports: [RouterLink, DatePipe, CountdownComponent],
  template: `
    <section class="wrap">
      <h2 class="page-title">{{ i.t('orders.title') }}</h2>
      @if (message()) { <div class="alert alert-ok">{{ message() }}</div> }
      @if (failMsg()) { <div class="alert alert-error">{{ failMsg() }}</div> }

      @if (orders(); as list) {
        @for (o of list; track o.id) {
          <article class="order panel">
            <header>
              <div>
                <h3>{{ i.t('orders.order') }} #{{ o.id }}</h3>
                <span class="muted">{{ o.created_at | date: 'medium' }} · {{ o.shipping_address }}</span>
              </div>
              @if (isExpired(o)) {
                <span class="status s-expired">{{ i.t('status.expired') }}</span>
              } @else {
                <span class="status" [class]="'status s-' + o.status">{{ i.t('status.' + o.status) }}</span>
              }
            </header>

            <ol class="track" [attr.aria-label]="i.t('status.' + o.status)">
              @for (s of steps; track s; let idx = $index) {
                <li [class.done]="stepIndex(o) >= idx" [class.cancelled]="o.status === 'cancelled'">{{ i.t('status.' + s) }}</li>
              }
            </ol>

            <ul class="items">
              @for (it of o.items; track it.id) {
                <li>
                  <span class="it-name">
                    <a [routerLink]="['/product', it.product.id]">{{ i.pick(it.product) }}</a>
                    @if (it.refunded_quantity) { <small class="returned">{{ i.t('refund.returned', { n: it.refunded_quantity }) }}</small> }
                  </span>
                  <span class="muted">× {{ it.quantity }} · \${{ it.unit_price }}</span>
                  <span>\${{ it.line_total }}</span>
                </li>
              }
            </ul>

            <footer>
              <span class="muted">{{ i.t('orders.payment') }}: {{ o.payment_method ? i.t('pay.' + o.payment_method) : '–' }}
                @if (o.card_last4) { · {{ o.card_brand?.toUpperCase() }} •••• {{ o.card_last4 }} }
                @if (o.installment_months) { · 0-0-{{ o.installment_months }} }
                @if (isExpired(o)) { <span class="pay-badge p-failed">{{ i.t('status.unpaid') }}</span> }
                @else if (o.payment_status) { <span class="pay-badge" [class]="'pay-badge p-' + o.payment_status">{{ i.t('status.' + o.payment_status) }}</span> }</span>
              <strong class="sum">\${{ o.total_amount }}</strong>
            </footer>

            @if (o.refunds?.length) {
              <div class="refunds">
                <div class="refunds-head">
                  <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M9 14L4 9l5-5M4 9h10a6 6 0 0 1 0 12h-3"/></svg>
                  <strong>{{ i.t('refund.title') }}</strong>
                  <span>{{ i.t('refund.total', { sum: o.refunded_amount ?? '0.00', of: o.total_amount }) }}</span>
                </div>
                <ul>
                  @for (r of o.refunds; track r.id) {
                    <li>
                      <span>{{ i.pick(r) }} × {{ r.quantity }} <small class="muted">· {{ i.t('refund.reason.' + r.reason) }} · {{ r.created_at | date: 'd MMM, HH:mm' }}</small></span>
                      <b>−\${{ r.amount }}</b>
                    </li>
                  }
                </ul>
                @if (o.card_last4) { <p class="muted small">{{ i.t('refund.toCard', { card: (o.card_brand ?? '').toUpperCase() + ' •••• ' + o.card_last4 }) }}</p> }
              </div>
            }

            @if (isExpired(o)) {
              <div class="expired-row">
                <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 3h6"/></svg>
                <span>{{ i.t('timer.expiredRow') }}</span>
              </div>
            }
            @if (o.payment_status === 'pending' && o.expires_at && (o.payment_method === 'qr' || o.payment_method === 'bank_transfer')) {
              <div class="pay-row">
                <app-countdown class="compact" [expiresAt]="o.expires_at" [totalSeconds]="totalSeconds(o)" (expired)="reload()" />
                <span class="pay-text">{{ i.t(o.payment_method === 'qr' ? 'timer.qrHint' : 'timer.transferHint') }}</span>
                @if (o.payment_method === 'qr' && o.qr_token) {
                  <a class="btn btn-primary" [href]="links.link(o.qr_token)" target="_blank" rel="noopener">{{ i.t('qr.open') }}</a>
                }
              </div>
            }

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
    </section>
  `,
  styles: [`
    .page-title { font-size: 1.5rem; margin-bottom: 1rem; }
    .s-expired { background: #f3eceb; color: #9a4a42; }
    .it-name { display: flex; flex-direction: column; min-width: 0; }
    .returned { color: #466b9b; font-size: .78rem; font-weight: 600; }
    .refunds { margin-top: 1rem; border-radius: 12px; background: #f1f5fb; padding: .9rem 1.1rem; }
    .refunds-head { display: flex; align-items: center; gap: .5rem; flex-wrap: wrap; color: #2f4f7a; }
    .refunds-head span { margin-left: auto; font-weight: 600; font-size: .88rem; }
    .refunds-head svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .refunds ul { list-style: none; margin: .6rem 0 0; padding: 0; }
    .refunds li { display: flex; justify-content: space-between; gap: 1rem; padding: .4rem 0; border-top: 1px solid #dde6f2; font-size: .9rem; }
    .refunds b { color: #2f4f7a; white-space: nowrap; }
    .refunds p { margin: .5rem 0 0; }
    .expired-row { display: flex; align-items: center; gap: .55rem; margin-top: 1rem; padding: .75rem 1rem; border-radius: 12px;
                   background: #f8f1f0; color: #8a3f37; font-size: .9rem; font-weight: 500; }
    .expired-row svg, .pay-row svg { flex: none; }
    .expired-row svg { width: 20px; height: 20px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }
    .pay-row { display: flex; align-items: center; gap: .9rem 1.2rem; flex-wrap: wrap; margin-top: 1rem; padding: .75rem 1rem;
               border-radius: 12px; background: var(--amber-50, #fff7e6); }
    .pay-text { flex: 1 1 220px; color: #7a5410; font-size: .9rem; font-weight: 500; }
    .qr-row { display: flex; justify-content: space-between; align-items: center; gap: 1rem; background: var(--amber-50, #fff7e6); border-radius: 12px; padding: .7rem 1rem; margin-top: .8rem; font-weight: 600; }
    .pay-badge { display: inline-block; margin-left: .3rem; padding: .05em .55em; border-radius: 6px; font-size: .78rem; font-weight: 700; background: #eef2ed; color: #5a6d61; }
    .p-paid { background: #e7f3e9; color: #267247; } .p-pending { background: #fff3dc; color: #956111; }
    .p-failed { background: #fbecea; color: #aa4942; } .p-refunded { background: #e8eff9; color: #466b9b; }
    .order { margin-bottom: 1.2rem; }
    header { display: flex; justify-content: space-between; align-items: flex-start; gap: 1rem; }
    h3 { font-size: 1.25rem; margin-bottom: .2rem; }
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
export class OrdersComponent implements OnInit, OnDestroy {
  readonly links = inject(PayLinkService);
  private qrPoll?: ReturnType<typeof setInterval>;

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
    this.links.ensure();
    // a QR may be paid from a phone at any moment: refresh while such an order is waiting
    this.qrPoll = setInterval(() => {
      if ((this.orders() ?? []).some(o => o.payment_method === 'qr' && o.payment_status === 'pending')) this.reload();
    }, 3000);
    this.api.orders().subscribe({ next: o => this.orders.set(o), error: () => this.error.set(true) });
  }

  ngOnDestroy() {
    clearInterval(this.qrPoll);
  }

  isExpired(o: Order): boolean {
    return o.status === 'cancelled' && o.failure_reason === 'Payment time is over.';
  }

  totalSeconds(o: Order): number {
    if (!o.expires_at) return 900;
    return Math.max(60, Math.round((new Date(o.expires_at).getTime() - new Date(o.created_at).getTime()) / 1000));
  }

  /** the timer reached 0: the server cancels the order, we show the new state */
  reload() {
    setTimeout(() => this.api.orders().subscribe({ next: o => this.orders.set(o), error: () => {} }), 300);
  }

  payQr(o: Order) {
    this.busy.set(true);
    this.api.payQr(o.id).subscribe({
      next: updated => {
        this.orders.update(list => (list ?? []).map(x => (x.id === updated.id ? updated : x)));
        this.busy.set(false);
      },
      error: e => {
        if (e.error?.order) this.orders.update(list => (list ?? []).map(x => (x.id === o.id ? e.error.order : x)));
        else this.failMsg.set(e.error?.detail ?? this.i.t('common.error'));
        this.busy.set(false);
      },
    });
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
