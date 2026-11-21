import { Injectable, inject, signal } from '@angular/core';

import { I18nService } from './i18n.service';

export type CurrencyCode = 'USD' | 'KZT' | 'EUR' | 'RUB';

/** Fixed rates for this demonstration shop; product/order amounts are stored in USD. */
export const CURRENCIES: readonly {
  code: CurrencyCode; name: string; label: string; symbol: string; rate: number;
}[] = [
  { code: 'USD', name: 'US dollar', label: 'USD · US dollar', symbol: '$', rate: 1 },
  { code: 'KZT', name: 'Kazakhstani tenge', label: 'KZT · Kazakhstani tenge', symbol: '₸', rate: 500 },
  { code: 'EUR', name: 'Euro', label: 'EUR · Euro', symbol: '€', rate: 0.92 },
  { code: 'RUB', name: 'Russian ruble', label: 'RUB · Russian ruble', symbol: '₽', rate: 90 },
];

@Injectable({ providedIn: 'root' })
export class CurrencyService {
  private readonly i = inject(I18nService);
  readonly currency = signal<CurrencyCode>('USD');

  use(code: string) {
    this.currency.set(CURRENCIES.find(c => c.code === code)?.code ?? 'USD');
  }

  fromBase(value: string | number | null | undefined): number {
    const amount = Number(value ?? 0);
    const rate = CURRENCIES.find(c => c.code === this.currency())!.rate;
    return (Number.isFinite(amount) ? amount : 0) * rate;
  }

  toBase(value: string | number): number {
    const amount = Number(value);
    const rate = CURRENCIES.find(c => c.code === this.currency())!.rate;
    return Number.isFinite(amount) ? amount / rate : 0;
  }

  /** Numeric values for price-filter inputs; empty URL values must stay empty. */
  inputValue(value: string | number | null | undefined): number | '' {
    return value === null || value === undefined || value === '' ? '' : Number(this.fromBase(value).toFixed(2));
  }

  format(value: string | number | null | undefined): string {
    const locale = { en: 'en-US', ru: 'ru-RU', kk: 'kk-KZ' }[this.i.lang()];
    return new Intl.NumberFormat(locale, {
      style: 'currency', currency: this.currency(), currencyDisplay: 'narrowSymbol',
      minimumFractionDigits: 2, maximumFractionDigits: 2,
    }).format(this.fromBase(value));
  }
}
