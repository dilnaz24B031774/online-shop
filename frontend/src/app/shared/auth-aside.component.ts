import { Component, inject } from '@angular/core';

import { I18nService } from '../core/i18n.service';

/** Green side panel on the sign-in and registration pages. */
@Component({
  selector: 'app-auth-aside',
  template: `
    <svg class="pattern" aria-hidden="true">
      <defs>
        <pattern id="auth-horn" width="56" height="56" patternUnits="userSpaceOnUse">
          <path d="M28 46V31M28 31C28 17 13 13 10 24c-1 7 7 8 8 3M28 31c0-14 15-18 18-7 1 7-7 8-8 3"
                fill="none" stroke="#F6A623" stroke-width="2" stroke-linecap="round" opacity=".18"/>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#auth-horn)"/>
    </svg>
    <div class="content">
      <h2>{{ i.t('auth.asideTitle') }}</h2>
      <p>{{ i.t('auth.asideText') }}</p>
      <ul>
        <li>{{ i.t('perk.delivery') }}</li>
        <li>{{ i.t('perk.pay') }}</li>
        <li>{{ i.t('perk.lang') }}</li>
      </ul>
    </div>
  `,
  styles: [`
    :host { position: relative; display: block; height: 100%; background: var(--green-900); color: #d5e6de; overflow: hidden; }
    .pattern { position: absolute; inset: 0; width: 100%; height: 100%; }
    .content { position: relative; padding: 2.4rem; display: flex; flex-direction: column; justify-content: flex-end; height: 100%; }
    h2 { color: #fff; font-size: 1.6rem; }
    ul { list-style: none; padding: 0; margin: 1rem 0 0; display: flex; flex-direction: column; gap: .6rem; }
    li { padding-left: 1.6rem; position: relative; font-size: .92rem; }
    li::before {
      content: ''; position: absolute; left: 0; top: .35em; width: 14px; height: 14px; border-radius: 50%;
      background: var(--amber);
    }
  `],
})
export class AuthAsideComponent {
  readonly i = inject(I18nService);
}
