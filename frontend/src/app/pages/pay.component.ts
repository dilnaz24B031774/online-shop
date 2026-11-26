import { Component, OnDestroy, computed, inject, input, signal } from '@angular/core';
import { DatePipe } from '@angular/common';

import { ApiService } from '../core/api.service';
import { I18nService, LANGS } from '../core/i18n.service';
import { QrInfo } from '../core/models';
import { CountdownComponent } from '../shared/countdown.component';

/** /pay/:token - the page a phone opens after scanning the QR. Plays the role of the bank app. */
@Component({
  selector: 'app-pay',
  imports: [DatePipe, CountdownComponent],
  template: `
    <div class="bank">
      <header class="bank-top">
        <span class="logo">
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="2.5" y="5" width="19" height="14" rx="3"/><path d="M2.5 10h19M6.5 15h4"/></svg>
          SaudaGo Pay
        </span>
        <span class="tag">{{ i.t('pay.secureTag') }}</span>
      </header>

      <main class="sheet">
        @if (loading()) {
          <div class="state"><span class="spinner" aria-hidden="true"></span><p>{{ i.t('pay.loading') }}</p></div>
        } @else if (info()) {
          @let q = info()!;
          @switch (q.state) {
            @case ('pending') {
              <p class="to">{{ i.t('pay.to') }}</p>
              <div class="merchant">
                <span class="m-logo" aria-hidden="true">S</span>
                <div><strong>{{ q.shop }}</strong><small>{{ i.t('pay.order', { n: q.order_id }) }} · {{ i.t('pay.items', { n: q.items }) }}</small></div>
              </div>
              <p class="amount">\${{ q.amount }}</p>
              <div class="timer"><app-countdown [expiresAt]="q.expires_at" [totalSeconds]="total(q)" (expired)="reload()" /></div>
              <ul class="facts">
                <li><span>{{ i.t('pay.method') }}</span><b>{{ i.t('pay.qr') }}</b></li>
                <li><span>{{ i.t('pay.fee') }}</span><b>$0.00</b></li>
              </ul>
              @if (error()) { <p class="err" role="alert">{{ error() }}</p> }
              <button type="button" class="pay" (click)="pay()" [disabled]="busy()">
                @if (busy()) { <span class="spinner small" aria-hidden="true"></span> }
                {{ i.t('pay.confirm', { sum: q.amount }) }}
              </button>
              <p class="note">{{ i.t('pay.secureNote') }}</p>
            }
            @case ('paid') {
              <div class="state ok">
                <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30"/><path d="M19 33l9 9 17-18"/></svg>
                <h1>{{ i.t('pay.done') }}</h1>
                <p class="amount small">\${{ q.amount }}</p>
                <p>{{ i.t('pay.doneText', { n: q.order_id }) }}</p>
                @if (q.paid_at) { <small class="muted">{{ q.paid_at | date: 'd MMM, HH:mm' }} · {{ q.paid_device }}</small> }
              </div>
            }
            @case ('expired') {
              <div class="state bad">
                <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30"/><path d="M32 20v13l8 5"/></svg>
                <h1>{{ i.t('pay.expired') }}</h1>
                <p>{{ i.t('pay.expiredText') }}</p>
              </div>
            }
            @default {
              <div class="state bad">
                <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30"/><path d="M24 24l16 16M40 24L24 40"/></svg>
                <h1>{{ i.t('pay.cancelled') }}</h1>
                <p>{{ i.t('pay.cancelledText') }}</p>
              </div>
            }
          }
        } @else {
          <div class="state bad">
            <svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="32" r="30"/><path d="M32 20v16M32 44h.01"/></svg>
            <h1>{{ i.t('pay.notFound') }}</h1>
            <p>{{ i.t('pay.notFoundText') }}</p>
          </div>
        }
      </main>

      <footer class="bank-foot">
        <div class="langs" role="group" aria-label="Language">
          @for (l of langs; track l.code) {
            <button type="button" [class.on]="i.lang() === l.code" (click)="i.use(l.code)">{{ l.label }}</button>
          }
        </div>
        <span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V7a4 4 0 0 1 8 0v4"/></svg>
          {{ i.t('pay.secure') }}
        </span>
      </footer>
    </div>
  `,
  styles: [`
    :host { display: block; min-height: 100vh; min-height: 100dvh; background: linear-gradient(180deg, #0e3b2e 0, #0e3b2e 210px, var(--soft) 210px); }
    .bank { max-width: 440px; margin: 0 auto; padding: 0 16px 24px; min-height: 100vh; min-height: 100dvh; display: flex; flex-direction: column; }
    .bank-top { display: flex; justify-content: space-between; align-items: center; padding: 18px 4px 22px; color: #fff; }
    .logo { display: inline-flex; align-items: center; gap: .5rem; font: 800 1.2rem var(--font-head, var(--font-body)); }
    .logo svg { width: 26px; height: 26px; fill: none; stroke: var(--amber); stroke-width: 2; stroke-linecap: round; }
    .tag { font-size: .72rem; font-weight: 700; background: rgba(255,255,255,.14); padding: .3em .7em; border-radius: 999px; }
    .sheet { background: var(--surface, #fff); border-radius: 22px; padding: 24px 20px; box-shadow: 0 24px 50px -30px rgba(14,59,46,.55); }
    .to { margin: 0 0 .7rem; color: var(--muted); font-size: .86rem; }
    .merchant { display: flex; align-items: center; gap: .8rem; }
    .merchant div { display: flex; flex-direction: column; }
    .merchant small { color: var(--muted); font-size: .82rem; }
    .m-logo { width: 46px; height: 46px; border-radius: 14px; background: #155a45; color: var(--amber); display: grid; place-items: center; font: 800 1.3rem var(--font-body); }
    .amount { font: 800 2.6rem var(--font-head, var(--font-body)); color: var(--green-900); margin: 1.1rem 0 .6rem; letter-spacing: -.02em; font-variant-numeric: tabular-nums; }
    .amount.small { font-size: 1.8rem; margin: .2rem 0 .4rem; }
    .timer { padding: .6rem 0 1rem; border-bottom: 1px solid var(--line); }
    .facts { list-style: none; margin: .4rem 0 1.2rem; padding: 0; }
    .facts li { display: flex; justify-content: space-between; padding: .55rem 0; font-size: .92rem; border-bottom: 1px dashed var(--line); }
    .facts span { color: var(--muted); }
    .pay { width: 100%; border: 0; border-radius: 16px; padding: 1.05rem; cursor: pointer; background: var(--green-700); color: #fff;
           font: 700 1.05rem var(--font-body); display: inline-flex; align-items: center; justify-content: center; gap: .6rem; }
    .pay:hover:not(:disabled) { background: var(--green-900); }
    .pay:disabled { opacity: .7; cursor: default; }
    .note { margin: .9rem 0 0; color: var(--muted); font-size: .8rem; text-align: center; }
    .err { background: #fbecea; color: #9a3a31; border-radius: 12px; padding: .7rem .9rem; font-size: .88rem; }
    .state { text-align: center; padding: 1.2rem .4rem; }
    .state svg { width: 76px; height: 76px; fill: none; stroke-width: 4; stroke-linecap: round; stroke-linejoin: round; margin-bottom: .6rem; }
    .state.ok svg circle { fill: #e3f4ea; stroke: none; } .state.ok svg path { stroke: #2f8f5b; }
    .state.bad svg circle { fill: #fbecea; stroke: none; } .state.bad svg path { stroke: #c2453a; }
    .state h1 { font-size: 1.45rem; margin: 0 0 .4rem; }
    .state p { color: var(--muted); margin: .3rem 0; }
    .spinner { width: 34px; height: 34px; border: 3px solid var(--line); border-top-color: var(--green-700); border-radius: 50%;
               display: inline-block; animation: spin .8s linear infinite; }
    .spinner.small { width: 18px; height: 18px; border-color: rgba(255,255,255,.35); border-top-color: #fff; }
    @keyframes spin { to { transform: rotate(360deg); } }
    .bank-foot { margin-top: auto; padding-top: 22px; display: flex; flex-direction: column; align-items: center; gap: .7rem; color: var(--muted); font-size: .8rem; }
    .bank-foot span { display: inline-flex; align-items: center; gap: .35rem; }
    .bank-foot svg { width: 15px; height: 15px; fill: none; stroke: currentColor; stroke-width: 1.8; }
    .langs { display: flex; gap: 4px; }
    .langs button { border: 1px solid var(--line); background: var(--surface, #fff); border-radius: 8px; padding: .3em .7em; font: 600 .78rem var(--font-body); cursor: pointer; color: var(--muted); }
    .langs button.on { background: var(--green-700); border-color: var(--green-700); color: #fff; }
  `],
})
export class PayComponent implements OnDestroy {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  readonly langs = LANGS;

  readonly token = input.required<string>();     // from /pay/:token
  readonly info = signal<QrInfo | null>(null);
  readonly loading = signal(true);
  readonly busy = signal(false);
  readonly error = signal('');
  private poll?: ReturnType<typeof setInterval>;

  ngOnInit() {
    this.reload();
    // if it was paid from another device, this page also shows it
    this.poll = setInterval(() => { if (this.info()?.state === 'pending') this.reload(true); }, 5000);
  }

  ngOnDestroy() {
    clearInterval(this.poll);
  }

  total(q: QrInfo): number {
    return Math.max(60, Math.round((new Date(q.expires_at).getTime() - new Date(q.created_at).getTime()) / 1000));
  }

  reload(silent = false) {
    if (!silent) this.loading.set(true);
    this.api.qrInfo(this.token()).subscribe({
      next: q => { this.info.set(q); this.loading.set(false); },
      error: () => { this.info.set(null); this.loading.set(false); },
    });
  }

  pay() {
    this.busy.set(true);
    this.error.set('');
    this.api.qrPay(this.token()).subscribe({
      next: q => { this.info.set(q); this.busy.set(false); },
      error: e => {
        this.busy.set(false);
        const state = e.error?.state;
        if (state) this.reload(true);
        else this.error.set(this.i.t('pay.network'));
      },
    });
  }
}
