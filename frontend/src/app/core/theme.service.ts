import { Injectable, inject, signal } from '@angular/core';
import { DOCUMENT } from '@angular/common';

export type Theme = 'light' | 'dark';
const KEY = 'sauda.theme';

/**
 * Light / dark theme.
 * The choice is saved in localStorage and written to  <html data-theme="light|dark">.
 * All dark colours live in src/theme.scss.
 */
@Injectable({ providedIn: 'root' })
export class ThemeService {
  private doc = inject(DOCUMENT);
  readonly theme = signal<Theme>(this.stored());

  constructor() {
    this.apply(this.theme());
  }

  use(theme: Theme) {
    this.theme.set(theme);
    this.apply(theme);
    try { localStorage.setItem(KEY, theme); } catch { /* private mode */ }
  }

  private apply(theme: Theme) {
    this.doc.documentElement.setAttribute('data-theme', theme);
  }

  private stored(): Theme {
    try { return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light'; } catch { return 'light'; }
  }
}
