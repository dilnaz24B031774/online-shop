import { Injectable, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';

export type Theme = 'light' | 'dark';
export type Accent = 'green' | 'blue' | 'violet';
export const ACCENTS: readonly { id: Accent; color: string }[] = [
  { id: 'green', color: '#155a45' },
  { id: 'blue', color: '#245aa1' },
  { id: 'violet', color: '#7045a6' },
];
const KEY = 'sauda.theme';
const ACCENT_KEY = 'sauda.accent';

/**
 * Light / dark theme.
 * The choice is saved in localStorage and written to  <html data-theme="light|dark">.
 * All dark colours live in src/theme.scss.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private doc = inject(DOCUMENT);
  readonly theme = signal<Theme>(this.stored());
  readonly accent = signal<Accent>(this.storedAccent());

  constructor() {
    this.apply(this.theme());
    this.doc.documentElement.setAttribute('data-accent', this.accent());
  }

  use(theme: Theme) {
    if (theme !== 'light' && theme !== 'dark') return;
    this.theme.set(theme);
    this.apply(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* private mode */ }
  }

  useAccent(accent: Accent) {
    if (!ACCENTS.some(option => option.id === accent)) return;
    this.accent.set(accent);
    this.doc.documentElement.setAttribute('data-accent', accent);
    try { localStorage.setItem(ACCENT_KEY, accent); } catch { /* private mode */ }
  }

  private apply(theme: Theme) {
    this.doc.documentElement.setAttribute('data-theme', theme);
  }

  private stored(): Theme {
    try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
  }

  private storedAccent(): Accent {
    try {
      const accent = localStorage.getItem(ACCENT_KEY);
      return ACCENTS.find(option => option.id === accent)?.id ?? 'green';
    } catch { return 'green'; }
  }
}
