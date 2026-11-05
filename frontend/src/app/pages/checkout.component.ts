import { Component, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { Address, Order } from '../core/models';

@Component({
  selector: 'app-checkout',
  imports: [FormsModule, RouterLink],
  template: `
    <div class="container page">
      @if (placed(); as o) {
        <div class="panel done">
          <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30" fill="#E3F4EA"/><path d="M20 33l8 8 16-17" fill="none" stroke="#2F8F5B" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <h1>{{ i.t('checkout.done', { n: o.id }) }}</h1>
          <p>{{ i.t('checkout.doneText') }}</p>
          <p class="total">\${{ o.total_amount }} · {{ i.t('pay.' + o.payment_method) }}</p>
          <a routerLink="/orders" class="btn btn-primary">{{ i.t('checkout.toOrders') }}</a>
        </div>
      } @else {
        <h1>{{ i.t('checkout.title') }}</h1>
        <div class="layout">
          <div class="steps">
            <section class="panel">
              <h2>{{ i.t('checkout.address') }}</h2>
              <div class="options">
                @for (a of addresses(); track a.id) {
                  <label class="option" [class.on]="addressId === a.id">
                    <input type="radio" name="address" [value]="a.id" [(ngModel)]="addressId" />
                    <span><strong>{{ a.label }}</strong><br><span class="muted">{{ a.city }}, {{ a.street }}{{ a.apartment ? ', ' + a.apartment : '' }}</span></span>
                  </label>
                }
              </div>

              <details [open]="addresses().length === 0">
                <summary>{{ i.t('checkout.addAddress') }}</summary>
                <form class="addr" (ngSubmit)="saveAddress()">
                  <div class="field"><label>{{ i.t('checkout.label') }}</label><input name="label" [(ngModel)]="newAddress.label" /></div>
                  <div class="field"><label>{{ i.t('checkout.city') }}</label><input name="city" [(ngModel)]="newAddress.city" required /></div>
                  <div class="field wide"><label>{{ i.t('checkout.street') }}</label><input name="street" [(ngModel)]="newAddress.street" required /></div>
                  <div class="field"><label>{{ i.t('checkout.apartment') }}</label><input name="apartment" [(ngModel)]="newAddress.apartment" /></div>
                  <button class="btn btn-ghost" type="submit" [disabled]="!newAddress.city || !newAddress.street">{{ i.t('checkout.saveAddress') }}</button>
                </form>
              </details>
            </section>

            <section class="panel">
              <h2>{{ i.t('checkout.payment') }}</h2>
              <div class="options">
                @for (m of methods; track m) {
                  <label class="option" [class.on]="method === m">
                    <input type="radio" name="method" [value]="m" [(ngModel)]="method" />
                    <span><strong>{{ i.t('pay.' + m) }}</strong></span>
                  </label>
                }
              </div>
            </section>
          </div>

          <aside class="panel summary">
            @if (cart.cart(); as c) {
              @for (item of c.items; track item.id) {
                <div class="line"><span>{{ i.pick(item.product) }} × {{ item.quantity }}</span><span>\${{ item.line_total }}</span></div>
              }
              <div class="line total"><span>{{ i.t('cart.total') }}</span><strong>\${{ c.total }}</strong></div>
            }
            @if (error()) { <div class="alert alert-error">{{ error() }}</div> }
            <button class="btn btn-sun btn-block" type="button" (click)="place()"
                    [disabled]="busy() || !cart.count()">{{ i.t('checkout.place') }}</button>
          </aside>
        </div>
      }
    </div>
  `,
  styles: [`
    .layout { display: grid; grid-template-columns: 1fr 340px; gap: 1.6rem; align-items: start; }
    .steps { display: flex; flex-direction: column; gap: 1.2rem; }
    .options { display: grid; grid-template-columns: repeat(auto-fill, minmax(210px, 1fr)); gap: .7rem; margin-bottom: .8rem; }
    .option {
      display: flex; gap: .7rem; align-items: flex-start; border: 2px solid var(--line); border-radius: var(--r-md);
      padding: .8rem 1rem; cursor: pointer; font-weight: 400; margin: 0;
    }
    .option input { width: auto; margin-top: .3rem; accent-color: var(--teal); }
    .option.on { border-color: var(--teal); background: #f1fafb; }
    details summary { cursor: pointer; font-weight: 600; color: var(--teal-dark); margin: .4rem 0 1rem; }
    .addr { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; }
    .addr .wide { grid-column: span 2; }
    .addr button { justify-self: start; }
    .summary { position: sticky; top: 180px; }
    .line { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: .6rem; }
    .total { border-top: 2px dashed var(--line); padding-top: .8rem; margin: 1rem 0; font-size: 1.15rem; }
    .total strong { font-family: var(--font-display); font-size: 1.5rem; }
    .done { text-align: center; max-width: 620px; margin: 1rem auto; padding: 2.5rem; }
    .done svg { width: 72px; margin-bottom: 1rem; }
    .done h1 { font-size: clamp(1.5rem, 3vw, 2.1rem); }
    .done .total { border: 0; font-weight: 700; }
    @media (max-width: 820px) { .layout { grid-template-columns: 1fr; } .addr { grid-template-columns: 1fr; } .addr .wide { grid-column: auto; } }
  `],
})
export class CheckoutComponent implements OnInit {
  readonly i = inject(I18nService);
  readonly cart = inject(CartService);
  private api = inject(ApiService);

  readonly methods = ['card', 'bank_transfer', 'cash_on_delivery'];
  readonly addresses = signal<Address[]>([]);
  readonly placed = signal<Order | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');

  addressId: number | null = null;
  method = 'card';
  newAddress = { label: 'Home', city: '', street: '', apartment: '' };

  ngOnInit() {
    this.cart.load().subscribe({ error: () => {} });
    this.loadAddresses();
  }

  loadAddresses(selectId?: number) {
    this.api.addresses().subscribe(list => {
      this.addresses.set(list);
      this.addressId = selectId ?? list.find(a => a.is_default)?.id ?? list[0]?.id ?? null;
    });
  }

  saveAddress() {
    this.api.addAddress(this.newAddress).subscribe(a => {
      this.newAddress = { label: 'Home', city: '', street: '', apartment: '' };
      this.loadAddresses(a.id);
    });
  }

  place() {
    if (!this.addressId) { this.error.set(this.i.t('checkout.needAddress')); return; }
    this.busy.set(true);
    this.error.set('');
    this.api.checkout(this.addressId, this.method).subscribe({
      next: order => { this.placed.set(order); this.busy.set(false); this.cart.load().subscribe(); },
      error: e => { this.busy.set(false); this.error.set(e.error?.detail ?? this.i.t('common.error')); },
    });
  }
}
