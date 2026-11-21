import { UpperCasePipe } from '@angular/common';
import { DemoQrComponent } from '../shared/demo-qr.component';
import { CountdownComponent } from '../shared/countdown.component';
import { QrCodeComponent } from '../shared/qr-code.component';
import { RegionService } from '../core/region.service';
import { PayLinkService } from '../core/pay-link.service';
import { PayIconComponent } from '../shared/pay-icon.component';
import { Component, OnDestroy, OnInit, effect, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { CartService } from '../core/cart.service';
import { I18nService } from '../core/i18n.service';
import { Address, CardInput, Order, PromoCheck, SavedCard } from '../core/models';

@Component({
  selector: 'app-checkout',
  imports: [FormsModule, RouterLink, UpperCasePipe, PayIconComponent, DemoQrComponent, CountdownComponent, QrCodeComponent],
  template: `
    <div class="container page">
      @if (placed(); as o) {
        @if (o.status === 'cancelled' && o.failure_reason === 'Payment time is over.') {
        <div class="panel done expired">
          <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30" fill="#FBECEA"/><circle cx="32" cy="34" r="14" fill="none" stroke="#C2453A" stroke-width="4"/><path d="M32 27v8l5 3M27 16h10" fill="none" stroke="#C2453A" stroke-width="4" stroke-linecap="round"/></svg>
          <h1>{{ i.t('timer.expiredTitle') }}</h1>
          <p>{{ i.t('timer.expiredText', { n: o.id }) }}</p>
          <div class="done-actions">
            <a routerLink="/catalog" class="btn btn-primary">{{ i.t('timer.again') }}</a>
            <a routerLink="/orders" class="btn btn-ghost">{{ i.t('checkout.toOrders') }}</a>
          </div>
        </div>
        } @else {
        <div class="panel done">
          <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30" fill="#E3F4EA"/><path d="M20 33l8 8 16-17" fill="none" stroke="#2F8F5B" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/></svg>
          <h1>{{ i.t(o.status === 'paid' ? 'checkout.done' : 'checkout.accepted', { n: o.id }) }}</h1>
          <p>{{ i.t('checkout.doneText') }}</p>
          @if (o.qr_paid_device) {
            <p class="phone-paid">
              <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="7" y="2.5" width="10" height="19" rx="2.5"/><path d="M11 18.5h2"/></svg>
              <span>{{ i.t('qr.paidFrom', { device: o.qr_paid_device }) }}</span>
            </p>
          }
          <p class="total">\${{ o.total_amount }} · {{ i.t('pay.' + o.payment_method) }}
            @if (o.card_last4) { · {{ o.card_brand | uppercase }} •••• {{ o.card_last4 }} }
            · <span class="pay-badge" [class]="'pay-badge p-' + o.payment_status">{{ i.t('status.' + o.payment_status) }}</span>
          </p>
          @if (o.payment_method === 'qr' && o.payment_status === 'pending') {
            <div class="qr-pay">
              <div class="qr-col">
                @if (o.qr_token) {
                  <app-qr-code [value]="links.link(o.qr_token)" [label]="i.t('qr.title')" />
                  <a class="qr-open" [href]="links.link(o.qr_token)" target="_blank" rel="noopener">{{ i.t('qr.open') }} ↗</a>
                } @else {
                  <app-demo-qr [seed]="o.id" [label]="i.t('qr.title')" />
                }
              </div>
              <div>
                @if (o.expires_at) {
                  <div class="qr-timer">
                    <app-countdown [expiresAt]="o.expires_at" [totalSeconds]="totalSeconds(o)" (expired)="refreshOrder(o.id)" />
                    <span>{{ i.t('timer.qrHint') }}</span>
                  </div>
                }
                <strong>{{ i.t('qr.scanPhone') }}</strong>
                <ol class="qr-steps">
                  <li>{{ i.t('qr.step1') }}</li>
                  <li>{{ i.t('qr.step2') }}</li>
                  <li>{{ i.t('qr.step3') }}</li>
                </ol>
                <p class="qr-sum">\${{ o.total_amount }} · {{ i.t('transfer.purposeText', { n: o.id }) }}</p>
                <p class="qr-wait"><span class="pulse" aria-hidden="true"></span>{{ i.t('qr.waitingPhone') }}</p>
                <div class="net" [class]="'net net-' + links.kind()">
                  <div class="net-row">
                    <span class="net-dot" aria-hidden="true"></span>
                    <span>{{ i.t('qr.net.' + links.kind()) }}</span>
                  </div>
                  @if (links.kind() !== 'local') { <code class="net-host">{{ links.host() }}</code> }
                  @if (links.kind() !== 'public') {
                    <small>{{ i.t('qr.net.help') }}</small>
                    @if (links.canRefresh()) {
                      <button type="button" class="net-btn" (click)="links.refresh()" [disabled]="links.checking()">
                        {{ links.checking() ? i.t('qr.net.checking') : i.t('qr.net.refresh') }}
                      </button>
                    }
                  }
                </div>
              </div>
            </div>
          }
          @if (o.installment_months) {
            <p class="monthly">{{ i.t('inst.monthly') }}: <b>\${{ (+o.total_amount / o.installment_months).toFixed(2) }}</b> × {{ o.installment_months }}</p>
          }
          @if (o.payment_method === 'bank_transfer') {
            <dl class="requisites">
              <div><dt>{{ i.t('transfer.receiver') }}</dt><dd>ТОО «Sauda» (demo)</dd></div>
              <div><dt>IBAN</dt><dd>KZ00 0000 0000 0000 0000</dd></div>
              <div><dt>{{ i.t('transfer.amount') }}</dt><dd>\${{ o.total_amount }}</dd></div>
              <div><dt>{{ i.t('transfer.purpose') }}</dt><dd>{{ i.t('transfer.purposeText', { n: o.id }) }}</dd></div>
              @if (o.expires_at && o.payment_status === 'pending') {
                <div><dt>{{ i.t('timer.payUntil') }}</dt><dd>{{ until(o.expires_at) }}</dd></div>
              }
            </dl>
          }
          <a routerLink="/orders" class="btn btn-primary">{{ i.t('checkout.toOrders') }}</a>
        </div>
        }
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
                    <input type="radio" name="method" [value]="m" [(ngModel)]="method" (ngModelChange)="cardError.set(null)" />
                    <app-pay-icon [method]="m" />
                    <span class="opt-text"><strong>{{ i.t('pay.' + m) }}</strong><small>{{ i.t('pay.hint.' + m) }}</small></span>
                  </label>
                }
              </div>

              @if (method === 'card' && savedCards().length) {
                <div class="saved" role="radiogroup" [attr.aria-label]="i.t('saved.title')">
                  <div class="saved-head">
                    <strong>{{ i.t('saved.title') }}</strong>
                    <small>{{ i.t('saved.why', { n: recentDays() }) }}</small>
                  </div>
                  @for (c of savedCards(); track c.id) {
                    <div class="saved-row" [class.on]="cardMode() === c.id">
                      <label class="saved-pick">
                        <input type="radio" name="cardmode" [checked]="cardMode() === c.id" (change)="pickCard(c.id)" />
                        <span class="mini-card" [attr.data-brand]="c.brand">{{ brandName(c.brand) }}</span>
                        <span class="saved-info">
                          <b>•••• {{ c.last4 }}</b>
                          <small>{{ i.t('saved.expires') }} {{ pad(c.exp_month) }}/{{ c.exp_year % 100 }} · {{ i.t('saved.used') }} {{ ago(c.last_used_at) }}</small>
                        </span>
                      </label>
                      @if (cardMode() === c.id) {
                        <div class="saved-cvc" [class.bad]="cardError() === 'cvc'">
                          <label [for]="'scvc' + c.id">CVC</label>
                          <input [id]="'scvc' + c.id" name="scvc" type="password" inputmode="numeric" maxlength="4" placeholder="•••"
                                 autocomplete="cc-csc" [(ngModel)]="savedCvc" />
                        </div>
                      }
                      <button type="button" class="saved-del" (click)="removeCard(c)" [attr.aria-label]="i.t('saved.delete')">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 7h14M10 7V5h4v2M7 7l1 12h8l1-12"/></svg>
                      </button>
                    </div>
                  }
                  <label class="saved-row new" [class.on]="cardMode() === 'new'">
                    <span class="saved-pick">
                      <input type="radio" name="cardmode" [checked]="cardMode() === 'new'" (change)="pickCard('new')" />
                      <span class="mini-card plus" aria-hidden="true">+</span>
                      <span class="saved-info"><b>{{ i.t('saved.new') }}</b></span>
                    </span>
                  </label>
                </div>
              }
              @if (method === 'card' && cardMode() === 'new') {
                <div class="card-box">
                  <div class="card-visual" [attr.data-brand]="brand()">
                    <div class="chip" aria-hidden="true"></div>
                    <span class="brand">{{ brandLabel() }}</span>
                    <span class="num">{{ card.number || '•••• •••• •••• ••••' }}</span>
                    <div class="row">
                      <span>{{ card.holder || i.t('card.holderPh') }}</span>
                      <span>{{ card.expiry || 'MM/YY' }}</span>
                    </div>
                  </div>
                  <div class="card-fields">
                    <div class="field wide" [class.bad]="cardError() === 'number'">
                      <label for="cn">{{ i.t('card.number') }}</label>
                      <input id="cn" name="cn" inputmode="numeric" autocomplete="cc-number" maxlength="23"
                             placeholder="0000 0000 0000 0000" [ngModel]="card.number" (ngModelChange)="setNumber($event)" />
                    </div>
                    <div class="field wide" [class.bad]="cardError() === 'holder'">
                      <label for="ch">{{ i.t('card.holder') }}</label>
                      <input id="ch" name="ch" autocomplete="cc-name" [placeholder]="i.t('card.holderPh')"
                             [ngModel]="card.holder" (ngModelChange)="card.holder = $event.toUpperCase()" />
                    </div>
                    <div class="field" [class.bad]="cardError() === 'expiry'">
                      <label for="ce">{{ i.t('card.expiry') }}</label>
                      <input id="ce" name="ce" inputmode="numeric" autocomplete="cc-exp" maxlength="5" placeholder="MM/YY"
                             [ngModel]="card.expiry" (ngModelChange)="setExpiry($event)" />
                    </div>
                    <div class="field" [class.bad]="cardError() === 'cvc'">
                      <label for="cc">CVC</label>
                      <input id="cc" name="cc" type="password" inputmode="numeric" autocomplete="cc-csc" maxlength="4"
                             placeholder="•••" [(ngModel)]="card.cvc" />
                    </div>
                  </div>
                  <p class="safe">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
                    {{ i.t('card.safe') }}
                  </p>
                  <label class="save-card">
                    <input type="checkbox" name="savecard" [(ngModel)]="saveCard" />
                    <span>
                      <b>{{ i.t('saved.save') }}</b>
                      <small>{{ i.t('saved.saveHint') }}</small>
                    </span>
                  </label>
                  <p class="demo">{{ i.t('card.demo') }} <code>4242 4242 4242 4242</code> · {{ i.t('card.demoDecline') }} <code>4000 0000 0000 0002</code></p>
                </div>
              } @else if (method === 'qr') {
                <div class="info-box">
                  <strong>{{ i.t('qr.title') }}</strong>
                  <p>{{ i.t('qr.text') }}</p>
                  <p class="timer-line">
                    <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l3 2M9 3h6"/></svg>
                    {{ i.t('timer.qrInfo') }}
                  </p>
                </div>
              } @else if (method === 'installment') {
                <div class="info-box">
                  <strong>{{ i.t('inst.title') }}</strong>
                  <div class="months" role="radiogroup" [attr.aria-label]="i.t('inst.title')">
                    @for (m of months; track m) {
                      <button type="button" role="radio" [attr.aria-checked]="installmentMonths === m"
                              [class.on]="installmentMonths === m" (click)="installmentMonths = m">
                        <b>{{ m }}</b> {{ i.t('inst.mon') }}
                      </button>
                    }
                  </div>
                  <p class="monthly">{{ i.t('inst.monthly') }}: <b>\${{ monthly() }}</b> × {{ installmentMonths }} · {{ i.t('inst.noOver') }}</p>
                </div>
              } @else if (method === 'bank_transfer') {
                <div class="info-box">
                  <strong>{{ i.t('transfer.title') }}</strong>
                  <p>{{ i.t('transfer.text') }}</p>
                </div>
              } @else if (method === 'cash_on_delivery') {
                <div class="info-box"><p>{{ i.t('cash.text') }}</p></div>
              }
            </section>
          </div>

          <aside class="panel summary">
            @if (cart.cart(); as c) {
              @for (item of c.items; track item.id) {
                <div class="line"><span>{{ i.pick(item.product) }} × {{ item.quantity }}</span><span>\${{ item.line_total }}</span></div>
              }
              <div class="promo">
                <label for="promo">{{ i.t('promo.label') }}</label>
                @if (promo(); as pr) {
                  <div class="promo-ok">
                    <span>{{ i.t('promo.applied', { code: pr.code, p: pr.percent }) }}</span>
                    <button type="button" class="link" (click)="removePromo()">{{ i.t('promo.remove') }}</button>
                  </div>
                } @else {
                  <div class="promo-row">
                    <input id="promo" name="promo" [(ngModel)]="promoCode" [placeholder]="i.t('promo.placeholder')"
                           autocapitalize="characters" (keydown.enter)="applyPromo()" />
                    <button type="button" class="btn btn-ghost" (click)="applyPromo()" [disabled]="!promoCode.trim()">
                      {{ i.t('promo.apply') }}
                    </button>
                  </div>
                  @if (promoError()) { <small class="promo-err">{{ promoError() }}</small> }
                }
              </div>
              @if (promo(); as pr) {
                <div class="line"><span>{{ i.t('promo.subtotal') }}</span><span>\${{ c.total }}</span></div>
                <div class="line discount"><span>{{ i.t('promo.discount') }} −{{ pr.percent }}%</span><span>−\${{ pr.discount }}</span></div>
                <div class="line total"><span>{{ i.t('cart.total') }}</span><strong>\${{ pr.total }}</strong></div>
              } @else {
                <div class="line total"><span>{{ i.t('cart.total') }}</span><strong>\${{ c.total }}</strong></div>
              }
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
    .option { align-items: center; }
    .opt-text { display: flex; flex-direction: column; gap: .1rem; }
    .opt-text small { color: var(--ink-soft); font-size: .78rem; line-height: 1.3; }
    .months { display: flex; gap: .5rem; flex-wrap: wrap; margin: .7rem 0 .4rem; }
    .months button { border: 1.5px solid var(--line); background: var(--surface, #fff); border-radius: 10px; padding: .45rem .9rem; cursor: pointer; font: inherit; color: var(--ink); }
    .months button.on { border-color: var(--green-700); background: var(--green-700); color: #fff; }
    .monthly { margin: .4rem 0 0; }
    .qr-pay { display: flex; gap: 1.4rem; align-items: center; text-align: left; max-width: 520px; margin: 1rem auto 1.4rem;
              background: var(--soft); border-radius: 16px; padding: 1.2rem; }
    .qr-pay p { margin: .3rem 0; } .qr-sum { font-weight: 700; }
    .demo-note { display: block; margin-top: .5rem; font-size: .76rem; }
    .net { margin-top: .8rem; padding: .7rem .85rem; border-radius: 12px; border: 1px solid var(--line); background: var(--soft);
           display: grid; gap: .35rem; font-size: .82rem; }
    .net-row { display: flex; align-items: center; gap: .5rem; font-weight: 600; color: var(--text); }
    .net-dot { width: 9px; height: 9px; border-radius: 50%; background: #d9a400; flex: none; }
    .net-public .net-dot { background: #1f9d55; }
    .net-local .net-dot { background: #d64545; }
    .net-host { font-size: .8rem; color: var(--muted); word-break: break-all; }
    .net small { color: var(--muted); line-height: 1.4; }
    .net-btn { justify-self: start; border: 1.5px solid var(--line); background: var(--surface, #fff); color: var(--text);
               border-radius: 999px; padding: .35em .9em; font: 600 .78rem var(--font-body); cursor: pointer; }
    .net-btn:hover:not(:disabled) { border-color: var(--green-700); }
    .net-btn:disabled { opacity: .6; cursor: default; }
    @media (max-width: 560px) { .qr-pay { flex-direction: column; } }
    details summary { cursor: pointer; font-weight: 600; color: var(--teal-dark); margin: .4rem 0 1rem; }
    .addr { display: grid; grid-template-columns: 1fr 1fr; gap: 0 1rem; }
    .addr .wide { grid-column: span 2; }
    .addr button { justify-self: start; }
    .summary { position: sticky; top: 180px; }
    .line { display: flex; justify-content: space-between; gap: 1rem; margin-bottom: .6rem; }
    .promo { border-top: 1px solid var(--line); margin-top: .8rem; padding-top: .8rem; }
    .promo label { font-weight: 700; font-size: .88rem; display: block; margin-bottom: .4rem; }
    .promo-row { display: flex; gap: .5rem; }
    .promo-row input { flex: 1; min-width: 0; text-transform: uppercase; }
    .promo-ok { display: flex; justify-content: space-between; align-items: center; background: var(--green-50);
                color: var(--green-900); border-radius: 10px; padding: .55rem .8rem; font-weight: 600; font-size: .9rem; }
    .promo-err { color: var(--red); display: block; margin-top: .35rem; }
    .link { border: 0; background: none; color: var(--green-700); font-weight: 600; cursor: pointer; padding: 0; }
    .discount { color: var(--green-700); font-weight: 600; }
    /* saved cards */
    .saved { margin-top: 1.2rem; border: 1px solid var(--line); border-radius: 14px; overflow: hidden; }
    .saved-head { display: flex; justify-content: space-between; align-items: baseline; gap: .4rem 1rem; flex-wrap: wrap;
                  padding: .8rem 1rem; background: var(--soft); }
    .saved-head small { color: var(--muted); font-size: .8rem; }
    .saved-row { display: flex; align-items: center; gap: .8rem; padding: .75rem 1rem; border-top: 1px solid var(--line);
                 cursor: pointer; transition: background .15s; margin: 0; font-weight: 400; }
    .saved-row:hover { background: #fafcfb; }
    .saved-row.on { background: #f1f8f4; box-shadow: inset 3px 0 var(--green-700); }
    .saved-pick { display: flex; align-items: center; gap: .8rem; flex: 1; min-width: 0; cursor: pointer; margin: 0; font-weight: 400; }
    .saved-pick input { width: auto; margin: 0; accent-color: var(--green-700); }
    .mini-card { width: 52px; height: 34px; border-radius: 6px; display: grid; place-items: center; flex: none;
                 font: 800 .7rem var(--font-body); letter-spacing: .04em; color: #fff; background: linear-gradient(135deg, #155a45, #0e3b2e); }
    .mini-card[data-brand="visa"] { background: linear-gradient(135deg, #1a3a8f, #0f2363); }
    .mini-card[data-brand="mastercard"] { background: linear-gradient(135deg, #3b2a22, #17110e); }
    .mini-card[data-brand="mir"] { background: linear-gradient(135deg, #1f8a4c, #0d5c34); }
    .mini-card.plus { background: var(--surface, #fff); color: var(--green-700); border: 1.5px dashed #b9cfc5; font-size: 1.2rem; }
    .saved-info { display: flex; flex-direction: column; min-width: 0; }
    .saved-info b { font-variant-numeric: tabular-nums; letter-spacing: .03em; }
    .saved-info small { color: var(--muted); font-size: .8rem; }
    .saved-cvc { display: flex; align-items: center; gap: .5rem; }
    .saved-cvc label { margin: 0; font-size: .82rem; color: var(--muted); }
    .saved-cvc input { width: 74px; padding: .5em .6em; text-align: center; letter-spacing: .2em; }
    .saved-cvc.bad input { border-color: var(--red); box-shadow: 0 0 0 3px rgba(200, 60, 50, .12); }
    .saved-del { border: 0; background: none; cursor: pointer; padding: .35rem; border-radius: 8px; color: var(--muted); display: grid; }
    .saved-del:hover { background: #fbecea; color: var(--red); }
    .saved-del svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .save-card { grid-column: 1 / -1; display: flex; gap: .7rem; align-items: flex-start; margin: 0; padding: .8rem 1rem;
                 border: 1px solid var(--line); border-radius: 12px; cursor: pointer; font-weight: 400; }
    .save-card input { width: 18px; height: 18px; margin: .15rem 0 0; accent-color: var(--green-700); flex: none; }
    .save-card span { display: flex; flex-direction: column; }
    .save-card small { color: var(--muted); font-size: .8rem; }
    .timer-line { display: flex; align-items: center; gap: .45rem; color: var(--green-900); font-weight: 600; }
    .timer-line svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; flex: none; }
    .qr-col { display: flex; flex-direction: column; align-items: center; gap: .55rem; flex: none; }
    .qr-open { font-size: .82rem; font-weight: 600; color: var(--green-700); }
    .qr-steps { margin: .4rem 0 .6rem; padding-left: 1.2rem; color: var(--muted); font-size: .88rem; line-height: 1.5; }
    .qr-wait { display: flex; align-items: center; gap: .5rem; font-weight: 600; color: var(--green-900); font-size: .9rem; }
    .pulse { width: 10px; height: 10px; border-radius: 50%; background: #2f8f5b; box-shadow: 0 0 0 0 rgba(47,143,91,.6); animation: pulse 1.6s infinite; flex: none; }
    @keyframes pulse { 70% { box-shadow: 0 0 0 10px rgba(47,143,91,0); } 100% { box-shadow: 0 0 0 0 rgba(47,143,91,0); } }
    .phone-paid { display: inline-flex; align-items: center; gap: .5rem; background: #e7f5ec; color: #1f6b43; font-weight: 600;
                  border-radius: 999px; padding: .45em 1em; animation: pop .4s ease-out; }
    .phone-paid svg { width: 18px; height: 18px; flex: none; margin: 0; fill: none; stroke: currentColor; stroke-width: 1.8; stroke-linecap: round; }
    @keyframes pop { from { transform: scale(.85); opacity: 0; } to { transform: none; opacity: 1; } }
    .qr-timer { display: flex; align-items: center; gap: .9rem; padding: .2rem 0 .8rem; margin-bottom: .6rem; border-bottom: 1px solid var(--line); }
    .qr-timer span { color: var(--muted); font-size: .82rem; line-height: 1.35; }
    .done-actions { display: flex; gap: .7rem; justify-content: center; flex-wrap: wrap; }
    .card-box { margin-top: 1.2rem; display: grid; grid-template-columns: 280px 1fr; gap: 1.4rem; align-items: start; }
    .card-visual {
      aspect-ratio: 1.586; border-radius: 16px; padding: 1.1rem 1.2rem; color: #fff; position: relative;
      background: linear-gradient(135deg, #155a45, #0e3b2e 60%, #082a20); display: flex; flex-direction: column;
      justify-content: flex-end; gap: .7rem; box-shadow: 0 18px 30px -18px rgba(14, 59, 46, .7);
    }
    .card-visual[data-brand="visa"] { background: linear-gradient(135deg, #1a3a8f, #0f2363); }
    .card-visual[data-brand="mastercard"] { background: linear-gradient(135deg, #3b2a22, #17110e); }
    .card-visual[data-brand="mir"] { background: linear-gradient(135deg, #1f8a4c, #0d5c34); }
    .chip { position: absolute; top: 1.1rem; left: 1.2rem; width: 38px; height: 28px; border-radius: 6px; background: linear-gradient(135deg, #f6d27a, #c9a14a); }
    .brand { position: absolute; top: 1rem; right: 1.2rem; font-weight: 800; letter-spacing: .04em; font-size: 1rem; }
    .num { font-family: ui-monospace, monospace; font-size: 1.05rem; letter-spacing: .08em; }
    .card-visual .row { display: flex; justify-content: space-between; font-size: .72rem; text-transform: uppercase; opacity: .85; }
    .card-fields { display: grid; grid-template-columns: 1fr 1fr; gap: .8rem 1rem; }
    .card-fields .wide { grid-column: 1 / -1; }
    .card-fields .field { margin: 0; }
    .card-fields .bad input { border-color: var(--red); box-shadow: 0 0 0 3px rgba(200, 60, 50, .12); }
    .safe { grid-column: 1 / -1; display: flex; gap: .5rem; align-items: center; margin: 0; font-size: .84rem; color: var(--green-700); }
    .safe svg { width: 17px; height: 17px; fill: none; stroke: currentColor; stroke-width: 1.8; flex-shrink: 0; }
    .demo { grid-column: 1 / -1; margin: 0; font-size: .8rem; color: var(--ink-soft); }
    .demo code { background: var(--soft); padding: .1em .4em; border-radius: 4px; }
    .info-box { margin-top: 1.2rem; background: var(--green-50); border-radius: 12px; padding: 1rem 1.2rem; font-size: .92rem; }
    .info-box p { margin: .3rem 0 0; }
    .requisites { display: grid; gap: .5rem; margin: 1rem auto 1.4rem; max-width: 420px; text-align: left; background: var(--soft); border-radius: 12px; padding: 1rem 1.2rem; }
    .requisites div { display: flex; justify-content: space-between; gap: 1rem; }
    .requisites dt { color: var(--ink-soft); } .requisites dd { margin: 0; font-weight: 700; }
    .pay-badge { display: inline-block; padding: .1em .6em; border-radius: 6px; font-size: .85rem; font-weight: 700; background: #eef2ed; }
    .p-paid { background: #e7f3e9; color: #267247; } .p-pending { background: #fff3dc; color: #956111; }
    .p-failed { background: #fbecea; color: #aa4942; } .p-refunded { background: #e8eff9; color: #466b9b; }
    .total { border-top: 2px dashed var(--line); padding-top: .8rem; margin: 1rem 0; font-size: 1.15rem; }
    .total strong { font-family: var(--font-display); font-size: 1.5rem; }
    .done { text-align: center; max-width: 620px; margin: 1rem auto; padding: 2.5rem; }
    .done svg { width: 72px; margin-bottom: 1rem; }
    .done h1 { font-size: clamp(1.5rem, 3vw, 2.1rem); }
    .done .total { border: 0; font-weight: 700; }
    @media (max-width: 820px) { .card-box { grid-template-columns: 1fr; } .card-visual { max-width: 320px; } .layout { grid-template-columns: 1fr; } .addr { grid-template-columns: 1fr; } .addr .wide { grid-column: auto; } }
  `],
})
export class CheckoutComponent implements OnInit, OnDestroy {
  readonly i = inject(I18nService);
  readonly cart = inject(CartService);
  private api = inject(ApiService);

  readonly methods = ['card', 'qr', 'installment', 'bank_transfer', 'cash_on_delivery'];
  readonly months = [3, 6, 12, 24];
  installmentMonths = 12;
  readonly qrPaid = signal(false);
  readonly addresses = signal<Address[]>([]);
  readonly placed = signal<Order | null>(null);
  readonly busy = signal(false);
  readonly error = signal('');
  readonly promo = signal<PromoCheck | null>(null);
  readonly promoError = signal('');
  promoCode = '';
  readonly cardError = signal<string | null>(null);
  card = { number: '', holder: '', expiry: '', cvc: '' };

  // saved cards: offered only if the customer paid by card recently (the server decides)
  readonly links = inject(PayLinkService);
  readonly region = inject(RegionService);
  private qrPoll?: ReturnType<typeof setInterval>;
  readonly savedCards = signal<SavedCard[]>([]);
  readonly recentDays = signal(90);
  readonly cardMode = signal<'new' | number>('new');
  savedCvc = '';
  saveCard = false;

  addressId: number | null = null;
  method = 'card';
  newAddress = { label: 'Home', city: '', street: '', apartment: '' };
  /** the customer's city (chosen after sign-in) is filled in a new address */
  private readonly fillCity = effect(() => {
    const c = this.region.current();
    if (c && !this.newAddress.city) this.newAddress.city = this.i.pick(c);
  });

  ngOnInit() {
    this.cart.load().subscribe({ error: () => {} });
    this.loadAddresses();
    this.loadCards();
    this.links.ensure();
    // waiting for the phone: check the order every 2 seconds while a QR is on the screen
    this.qrPoll = setInterval(() => {
      const o = this.placed();
      if (o && o.payment_method === 'qr' && o.payment_status === 'pending') this.refreshOrder(o.id, 0);
    }, 2000);
  }

  ngOnDestroy() {
    clearInterval(this.qrPoll);
  }

  loadCards() {
    this.api.savedCards().subscribe({
      next: r => {
        this.savedCards.set(r.cards);
        this.recentDays.set(r.recent_days);
        const mode = this.cardMode();
        if (mode === 'new' && r.cards.length && !this.card.number) this.cardMode.set(r.cards[0].id);
        if (typeof mode === 'number' && !r.cards.some(c => c.id === mode)) this.cardMode.set(r.cards[0]?.id ?? 'new');
      },
      error: () => {},
    });
  }

  pickCard(mode: 'new' | number) {
    this.cardMode.set(mode);
    this.savedCvc = '';
    this.cardError.set(null);
    this.error.set('');
  }

  removeCard(c: SavedCard) {
    this.api.deleteCard(c.id).subscribe({ next: () => this.loadCards(), error: () => {} });
  }

  brandName(brand: string): string {
    return { visa: 'VISA', mastercard: 'MC', mir: 'МИР', amex: 'AMEX' }[brand] ?? 'CARD';
  }

  pad(n: number): string {
    return String(n).padStart(2, '0');
  }

  ago(date: string): string {
    const days = Math.floor((Date.now() - new Date(date).getTime()) / 86400000);
    return days <= 0 ? this.i.t('tp.today') : this.i.t('tp.daysAgo', { n: days });
  }

  // ---------- payment timer
  totalSeconds(o: Order): number {
    if (!o.expires_at) return 900;
    return Math.max(60, Math.round((new Date(o.expires_at).getTime() - new Date(o.created_at).getTime()) / 1000));
  }

  until(date: string): string {
    return new Date(date).toLocaleString(this.i.lang() === 'en' ? 'en-GB' : 'ru-RU',
      { day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit' });
  }

  /** the timer reached 0: ask the server (it cancels the order and returns the goods to the stock) */
  refreshOrder(id: number, delay = 800) {
    setTimeout(() => this.api.orders().subscribe({
      next: list => { const o = list.find(x => x.id === id); if (o) this.placed.set(o); },
      error: () => {},
    }), 800);
  }

  loadAddresses(selectId?: number) {
    this.api.addresses().subscribe(list => {
      this.addresses.set(list);
      this.addressId = selectId ?? list.find(a => a.is_default)?.id ?? list[0]?.id ?? null;
    });
  }

  saveAddress() {
    this.api.addAddress(this.newAddress).subscribe(a => {
      this.newAddress = { label: 'Home', city: this.region.current() ? this.i.pick(this.region.current()) : '', street: '', apartment: '' };
      this.loadAddresses(a.id);
    });
  }

  applyPromo() {
    const code = this.promoCode.trim();
    if (!code) return;
    this.promoError.set('');
    this.api.checkPromo(code).subscribe({
      next: r => this.promo.set(r),
      error: e => this.promoError.set(this.promoText(e.error)),
    });
  }

  /** server reason code -> text in the current language */
  promoText(err: { code?: string; detail?: string } | null): string {
    const code = err?.code;
    if (code && ['not_found', 'not_active', 'expired', 'used_up', 'min_order', 'already_used'].includes(code)) {
      const min = /\$([\d.]+)/.exec(err?.detail ?? '')?.[1] ?? '';
      return this.i.t('promo.err.' + code, { min });
    }
    return err?.detail ?? this.i.t('common.error');
  }

  removePromo() {
    this.promo.set(null);
    this.promoCode = '';
  }

  // ---------- card form helpers (checks in the browser; the server checks again)
  readonly brand = signal('card');

  brandLabel(): string {
    return { visa: 'VISA', mastercard: 'Mastercard', mir: 'МИР', amex: 'AMEX' }[this.brand()] ?? '';
  }

  setNumber(value: string) {
    const digits = value.replace(/\D/g, '').slice(0, 19);
    this.card.number = digits.replace(/(\d{4})(?=\d)/g, '$1 ');
    this.brand.set(/^4/.test(digits) ? 'visa' : /^(5[1-5]|2[2-7])/.test(digits) ? (/^220[0-4]/.test(digits) ? 'mir' : 'mastercard')
      : /^3[47]/.test(digits) ? 'amex' : 'card');
  }

  setExpiry(value: string) {
    const d = value.replace(/\D/g, '').slice(0, 4);
    this.card.expiry = d.length > 2 ? d.slice(0, 2) + '/' + d.slice(2) : d;
  }

  private luhn(num: string): boolean {
    let sum = 0;
    [...num].reverse().forEach((ch, i) => { let d = +ch; if (i % 2) { d *= 2; if (d > 9) d -= 9; } sum += d; });
    return sum % 10 === 0;
  }

  private checkCard(): string | null {
    const digits = this.card.number.replace(/\D/g, '');
    if (digits.length < 13 || !this.luhn(digits)) return 'number';
    if (this.card.holder.trim().length < 2) return 'holder';
    const m = /^(\d{2})\/(\d{2})$/.exec(this.card.expiry);
    const now = new Date();
    if (!m || +m[1] < 1 || +m[1] > 12 || (2000 + +m[2]) * 12 + +m[1] < now.getFullYear() * 12 + now.getMonth() + 1) return 'expiry';
    if (!/^\d{3,4}$/.test(this.card.cvc)) return 'cvc';
    return null;
  }

  monthly(): string {
    const total = +(this.promo()?.total ?? this.cart.cart()?.total ?? 0);
    return (total / this.installmentMonths).toFixed(2);
  }

  payQr(id: number) {
    this.busy.set(true);
    this.api.payQr(id).subscribe({
      next: order => { this.placed.set(order); this.busy.set(false); },
      error: e => {
        this.busy.set(false);
        if (e.error?.order) { this.placed.set(e.error.order); return; }       // time is over -> show it
        this.error.set(e.error?.detail ?? this.i.t('common.error'));
      },
    });
  }

  place() {
    if (!this.addressId) { this.error.set(this.i.t('checkout.needAddress')); return; }
    let card: CardInput | undefined;
    let saved: { id: number; cvc: string } | undefined;
    const mode = this.cardMode();
    if (this.method === 'card' && typeof mode === 'number') {
      if (!/^\d{3,4}$/.test(this.savedCvc)) { this.cardError.set('cvc'); this.error.set(this.i.t('card.err.cvc')); return; }
      saved = { id: mode, cvc: this.savedCvc };
    } else if (this.method === 'card') {
      const problem = this.checkCard();
      if (problem) { this.cardError.set(problem); this.error.set(this.i.t('card.err.' + problem)); return; }
      const [mm, yy] = this.card.expiry.split('/');
      card = { number: this.card.number, holder: this.card.holder.trim(), exp_month: +mm, exp_year: 2000 + +yy, cvc: this.card.cvc };
    }
    this.busy.set(true);
    this.error.set('');
    this.cardError.set(null);
    const months = this.method === 'installment' ? this.installmentMonths : undefined;
    this.api.checkout(this.addressId, this.method, this.promo()?.code ?? '', card, months, saved,
                      this.method === 'card' && !saved && this.saveCard).subscribe({
      next: order => {
        this.placed.set(order); this.busy.set(false); this.cart.load().subscribe();
        this.card = { number: '', holder: '', expiry: '', cvc: '' };          // forget the card data
        this.savedCvc = '';
      },
      error: e => {
        this.busy.set(false);
        this.card.cvc = '';
        this.savedCvc = '';
        if (e.status === 402) { this.error.set(this.i.t('card.declined')); return; }
        if (e.error?.code) { this.removePromo(); this.promoError.set(this.promoText(e.error)); this.error.set(this.promoText(e.error)); return; }
        if (e.error?.field === 'saved_card') { this.loadCards(); this.cardMode.set('new'); }
        if (e.error?.field) { this.cardError.set(e.error.field); this.error.set(this.i.t('card.err.' + e.error.field)); return; }
        this.error.set(e.error?.detail ?? this.i.t('common.error'));
      },
    });
  }
}
