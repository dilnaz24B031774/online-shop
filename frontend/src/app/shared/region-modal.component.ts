import { Component, computed, inject, signal } from '@angular/core';

import { I18nService } from '../core/i18n.service';
import { City } from '../core/models';
import { RegionService } from '../core/region.service';

/** "Are you from Almaty?" -> Yes / Choose another city (list with search). */
@Component({
  selector: 'app-region-modal',
  template: `
    @if (region.open()) {
      <div class="backdrop" (click)="region.close()"></div>
      <section class="modal" role="dialog" aria-modal="true" aria-labelledby="region-title">
        <button type="button" class="x" (click)="region.close()" [attr.aria-label]="i.t('common.close')">×</button>
        <div class="pin" aria-hidden="true">
          <svg viewBox="0 0 24 24"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/><circle cx="12" cy="9.5" r="2.5"/></svg>
        </div>

        @if (!region.showList() && region.suggested(); as s) {
          <h2 id="region-title">{{ i.t('region.question', { city: i.pick(s) }) }}</h2>
          <p class="sub">{{ i.t('region.why') }}</p>
          <div class="actions">
            <button type="button" class="btn btn-primary" [disabled]="region.saving()" (click)="region.choose(s)">{{ i.t('region.yes') }}</button>
            <button type="button" class="btn btn-ghost" (click)="region.showList.set(true)">{{ i.t('region.other') }}</button>
          </div>
        } @else {
          <h2 id="region-title">{{ i.t('region.choose') }}</h2>
          <input class="search" type="search" [value]="q()" (input)="q.set($any($event.target).value)"
                 [placeholder]="i.t('region.search')" [attr.aria-label]="i.t('region.search')" />
          <ul class="cities">
            @for (c of filtered(); track c.id) {
              <li>
                <button type="button" [class.on]="region.current()?.id === c.id" [disabled]="region.saving()" (click)="region.choose(c)">
                  <span class="name">{{ i.pick(c) }}</span>
                  <span class="days">{{ days(c) }}</span>
                </button>
              </li>
            } @empty {
              <li class="none">{{ i.t('region.none') }}</li>
            }
          </ul>
        }
      </section>
    }
  `,
  styles: [`
    .backdrop { position: fixed; inset: 0; background: rgba(8, 28, 22, .45); z-index: 900; animation: fade .15s ease; }
    .modal {
      position: fixed; z-index: 901; left: 50%; top: 50%; transform: translate(-50%, -50%);
      width: min(460px, calc(100vw - 32px)); max-height: calc(100vh - 48px); overflow: auto;
      background: var(--surface, #fff); color: var(--text); border-radius: 20px; padding: 1.8rem 1.6rem 1.5rem;
      box-shadow: 0 24px 60px -20px rgba(8, 40, 30, .45); text-align: center; animation: pop .18s ease;
    }
    .x { position: absolute; top: 10px; right: 12px; border: 0; background: none; font-size: 1.6rem; line-height: 1; color: var(--muted); cursor: pointer; padding: 4px 8px; border-radius: 8px; }
    .x:hover { background: var(--soft); }
    .pin { width: 56px; height: 56px; border-radius: 50%; background: var(--soft); display: grid; place-items: center; margin: 0 auto .9rem; }
    .pin svg { width: 28px; height: 28px; fill: none; stroke: var(--green-700); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
    h2 { margin: 0 0 .4rem; font-size: 1.35rem; }
    .sub { margin: 0 auto 1.3rem; color: var(--muted); font-size: .92rem; max-width: 34ch; }
    .actions { display: grid; gap: .6rem; }
    .actions .btn { width: 100%; justify-content: center; }
    .search { width: 100%; margin: .6rem 0 .8rem; }
    .cities { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: 1fr 1fr; gap: 8px; text-align: left; }
    .cities button {
      width: 100%; display: flex; flex-direction: column; gap: 2px; padding: .6rem .75rem; border-radius: 12px; cursor: pointer;
      border: 1.5px solid var(--line); background: var(--surface, #fff); color: var(--text); font: inherit; text-align: left;
    }
    .cities button:hover { border-color: var(--green-700); }
    .cities button.on { border-color: var(--green-700); background: var(--soft); }
    .name { font-weight: 600; font-size: .92rem; }
    .days { color: var(--muted); font-size: .76rem; }
    .none { grid-column: 1 / -1; color: var(--muted); text-align: center; padding: 1rem 0; }
    @keyframes fade { from { opacity: 0; } }
    @keyframes pop { from { opacity: 0; transform: translate(-50%, -46%) scale(.97); } }
    @media (max-width: 420px) { .cities { grid-template-columns: 1fr; } }
  `],
})
export class RegionModalComponent {
  readonly i = inject(I18nService);
  readonly region = inject(RegionService);

  readonly q = signal('');
  readonly filtered = computed(() => {
    const q = this.q().trim().toLowerCase();
    return this.region.cities().filter(c => !q || [c.name_en, c.name_ru, c.name_kk].some(n => n.toLowerCase().includes(q)));
  });

  days(c: City): string {
    return this.i.t('region.days', { min: c.delivery_days_min, max: c.delivery_days_max });
  }
}
