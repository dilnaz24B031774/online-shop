import { Component, computed, inject, input, signal, effect } from '@angular/core';
import { Router, RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { TopItem } from '../core/models';
import { ProductCardComponent } from '../shared/product-card.component';

type Kind = 'hits' | 'new' | 'trends';

/** Top: hits (real purchases), new arrivals, trends of the week. Tab and period live in the URL. */
@Component({
  selector: 'app-top',
  imports: [RouterLink, ProductCardComponent],
  template: `
    <div class="container page">
      <header class="head">
        <div>
          <p class="eyebrow">Sauda</p>
          <h1>{{ i.t('tp.title') }}</h1>
          <p class="lead">{{ i.t('tp.lead') }}</p>
        </div>
        <div class="tabs" role="tablist" [attr.aria-label]="i.t('tp.title')">
          @for (t of tabs; track t.kind) {
            <button type="button" role="tab" [attr.aria-selected]="current() === t.kind" [class.on]="current() === t.kind"
                    (click)="go(t.kind)">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path [attr.d]="t.icon"/></svg>
              {{ i.t('tp.' + t.kind) }}
            </button>
          }
        </div>
      </header>

      <div class="bar">
        <p class="how">
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 11v5M12 8h.01"/></svg>
          {{ i.t('tp.how.' + current()) }}
        </p>
        @if (current() === 'hits') {
          <div class="periods" role="radiogroup" [attr.aria-label]="i.t('tp.period')">
            @for (p of periods; track p) {
              <button type="button" role="radio" [attr.aria-checked]="currentPeriod() === p" [class.on]="currentPeriod() === p"
                      (click)="go('hits', p)">{{ i.t('tp.p.' + p) }}</button>
            }
          </div>
        }
      </div>

      @if (loading()) {
        <div class="grid">
          @for (n of [1, 2, 3, 4, 5]; track n) { <div class="skeleton"></div> }
        </div>
      } @else if (error()) {
        <div class="alert alert-error">{{ i.t('common.error') }}</div>
      } @else if (items().length === 0) {
        <div class="empty panel">
          <svg viewBox="0 0 48 48" aria-hidden="true"><path d="M8 38h32M14 38V24M24 38V14M34 38V28"/></svg>
          <h2>{{ i.t('tp.empty.' + current()) }}</h2>
          <p>{{ i.t('tp.emptyText') }}</p>
          <a routerLink="/catalog" class="btn btn-primary">{{ i.t('tp.toCatalog') }}</a>
        </div>
      } @else {
        <div class="grid">
          @for (it of items(); track it.product.id; let idx = $index) {
            <div class="item">
              <app-product-card [product]="it.product" [rank]="current() === 'new' ? null : idx + 1" />
              <div class="metric" [class.up]="current() === 'trends'">
                @switch (current()) {
                  @case ('hits') {
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 4h2.5l2.2 10.5h10.6L20.5 7H6.4"/></svg>
                    {{ i.t('tp.bought', { n: it.units ?? 0 }) }}
                  }
                  @case ('trends') {
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 17l6-6 4 4 8-8M15 7h6v6"/></svg>
                    @if (it.growth === null) { {{ i.t('tp.firstWeek', { n: it.units ?? 0 }) }} }
                    @else { +{{ it.growth }}% · {{ it.prev_units }} → {{ it.units }} {{ i.t('tp.pcs') }} }
                  }
                  @default {
                    <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 3l2.4 5 5.6.8-4 3.9.9 5.5L12 15.6 7.1 18.2l.9-5.5-4-3.9 5.6-.8z"/></svg>
                    {{ added(it.product.created_at) }}
                  }
                }
              </div>
            </div>
          }
        </div>
      }
    </div>
  `,
  styles: [`
    .head { display: flex; justify-content: space-between; align-items: flex-end; gap: 1.2rem 2rem; flex-wrap: wrap; margin-bottom: 1.2rem; }
    .eyebrow { margin: 0 0 .25rem; color: var(--green-700); font-weight: 700; font-size: .78rem; text-transform: uppercase; letter-spacing: .12em; }
    h1 { margin: 0; }
    .lead { margin: .35rem 0 0; color: var(--muted); max-width: 52ch; }
    .tabs { display: inline-flex; background: var(--soft); border-radius: 14px; padding: 5px; gap: 4px; }
    .tabs button {
      display: inline-flex; align-items: center; gap: .45rem; border: 0; background: transparent; cursor: pointer;
      font: 600 .92rem var(--font-body); color: var(--muted); padding: .6em 1.05em; border-radius: 10px; transition: background .15s, color .15s;
    }
    .tabs button:hover { color: var(--green-900); }
    .tabs button.on { background: #fff; color: var(--green-900); box-shadow: 0 2px 8px -3px rgba(14, 59, 46, .3); }
    .tabs svg { width: 18px; height: 18px; fill: none; stroke: currentColor; stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
    .tabs button.on svg { stroke: var(--amber); }

    .bar { display: flex; justify-content: space-between; align-items: center; gap: .8rem 1.5rem; flex-wrap: wrap;
           border-top: 1px solid var(--line); border-bottom: 1px solid var(--line); padding: .8rem 0; margin-bottom: 1.4rem; }
    .how { display: flex; align-items: center; gap: .5rem; margin: 0; color: var(--muted); font-size: .9rem; }
    .how svg { width: 18px; height: 18px; flex: none; fill: none; stroke: var(--green-700); stroke-width: 1.8; stroke-linecap: round; }
    .periods { display: flex; gap: 6px; flex-wrap: wrap; }
    .periods button {
      border: 1.5px solid var(--line); background: #fff; color: var(--text); cursor: pointer;
      font: 600 .84rem var(--font-body); padding: .4em .9em; border-radius: 999px;
    }
    .periods button:hover { border-color: var(--green-700); }
    .periods button.on { background: var(--green-700); border-color: var(--green-700); color: #fff; }

    .grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 16px; }
    .item { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
    .item app-product-card { flex: 1; height: auto; }
    .metric {
      display: flex; align-items: center; justify-content: center; gap: .4rem; border-radius: 10px;
      background: var(--soft); color: var(--green-900); font-weight: 600; font-size: .84rem; padding: .5em .6em; text-align: center;
    }
    .metric.up { background: #e7f5ec; color: #1f7a4a; }
    .metric svg { width: 16px; height: 16px; flex: none; fill: none; stroke: currentColor; stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

    .skeleton { height: 380px; border-radius: var(--r-md); background: linear-gradient(90deg, var(--soft), #fbfcfb, var(--soft));
                background-size: 200% 100%; animation: shine 1.2s infinite linear; }
    @keyframes shine { to { background-position: -200% 0; } }

    .empty { text-align: center; padding: 3rem 1.5rem; max-width: 560px; margin: 1rem auto; }
    .empty svg { width: 56px; height: 56px; fill: none; stroke: var(--green-700); stroke-width: 3; stroke-linecap: round; margin-bottom: .6rem; }
    .empty h2 { font-size: 1.25rem; margin-bottom: .4rem; }
    .empty p { color: var(--muted); margin: 0 auto 1.2rem; max-width: 42ch; }

    @media (max-width: 1150px) { .grid { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
    @media (max-width: 860px) { .grid { grid-template-columns: repeat(3, minmax(0, 1fr)); } }
    @media (max-width: 620px) {
      .grid { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; }
      .tabs { width: 100%; } .tabs button { flex: 1; justify-content: center; padding: .6em .4em; font-size: .85rem; }
    }
  `],
})
export class TopComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private router = inject(Router);

  readonly kind = input<string>();       // ?kind=hits|new|trends
  readonly period = input<string>();     // ?period=7|30|90|all

  readonly tabs: { kind: Kind; icon: string }[] = [
    { kind: 'hits', icon: 'M12 3c1 3 4 4.5 4 8.5a4 4 0 0 1-8 0c0-1.6.7-2.8 1.6-3.7.2 1.4 1 2.2 2 2.2 0-2.8-.6-4.6.4-7z' },
    { kind: 'trends', icon: 'M3 17l6-6 4 4 8-8M15 7h6v6' },
    { kind: 'new', icon: 'M12 3l2.4 5 5.6.8-4 3.9.9 5.5L12 15.6 7.1 18.2l.9-5.5-4-3.9 5.6-.8z' },
  ];
  readonly periods = ['7', '30', '90', 'all'];

  readonly current = computed<Kind>(() => (['hits', 'new', 'trends'].includes(this.kind() ?? '') ? this.kind() as Kind : 'hits'));
  readonly currentPeriod = computed(() => (this.periods.includes(this.period() ?? '') ? this.period()! : '30'));

  readonly items = signal<TopItem[]>([]);
  readonly loading = signal(true);
  readonly error = signal(false);

  constructor() {
    effect(() => {
      const kind = this.current(), period = this.currentPeriod();
      this.loading.set(true);
      this.error.set(false);
      this.api.top(kind, period).subscribe({
        next: r => { this.items.set(r.items); this.loading.set(false); },
        error: () => { this.error.set(true); this.loading.set(false); },
      });
    });
  }

  go(kind: Kind, period?: string) {
    this.router.navigate(['/top'], { queryParams: { kind, period: kind === 'hits' ? (period ?? this.currentPeriod()) : null } });
  }

  added(createdAt?: string): string {
    if (!createdAt) return this.i.t('tp.newBadge');
    const days = Math.floor((Date.now() - new Date(createdAt).getTime()) / 86400000);
    return days <= 0 ? this.i.t('tp.today') : this.i.t('tp.daysAgo', { n: days });
  }
}
