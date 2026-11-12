import { Component, input } from '@angular/core';

/** Simple own icons for payment methods (no bank logos). */
@Component({
  selector: 'app-pay-icon',
  template: `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      @switch (method()) {
        @case ('card') { <rect x="2.5" y="5" width="19" height="14" rx="2.5"/><path d="M2.5 9.5h19M6 15h4"/> }
        @case ('qr') {
          <rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>
          <rect x="3" y="14" width="7" height="7" rx="1"/><path d="M14 14h3v3h-3zM20 14v.01M14 20h.01M17 20h4v-3"/>
        }
        @case ('installment') {
          <rect x="3" y="4.5" width="18" height="16" rx="2.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>
          <path d="M7.5 14h2M11 14h2M14.5 14h2M7.5 17h2"/>
        }
        @case ('bank_transfer') { <path d="M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18"/> }
        @default { <rect x="2.5" y="6" width="19" height="12" rx="2"/><circle cx="12" cy="12" r="2.6"/><path d="M6 9.5v5M18 9.5v5"/> }
      }
    </svg>
  `,
  styles: [`
    :host { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px; background: var(--green-50); flex-shrink: 0; }
    svg { width: 23px; height: 23px; fill: none; stroke: var(--green-900); stroke-width: 1.7; stroke-linecap: round; stroke-linejoin: round; }
  `],
})
export class PayIconComponent {
  readonly method = input('card');
}
