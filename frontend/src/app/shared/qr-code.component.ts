import { Component, computed, effect, inject, input, signal } from '@angular/core';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';

/** A real QR code (scannable by any phone camera) for the given link. */
@Component({
  selector: 'app-qr-code',
  template: `<div class="qr" role="img" [attr.aria-label]="label()" [innerHTML]="svg()"></div>`,
  styles: [`
    :host { display: block; width: 200px; padding: 10px; background: #fff; border-radius: 14px; border: 1px solid var(--line); }
    .qr { line-height: 0; }
    .qr ::ng-deep svg { width: 100%; height: auto; display: block; }
  `],
})
export class QrCodeComponent {
  private sanitizer = inject(DomSanitizer);
  readonly value = input.required<string>();
  readonly label = input('QR');
  private readonly raw = signal('');
  // the SVG is made by the qrcode library from our own link, so it is safe to insert
  readonly svg = computed<SafeHtml>(() => this.sanitizer.bypassSecurityTrustHtml(this.raw()));

  constructor() {
    effect(() => {
      const value = this.value();
      // the library is loaded only when a QR is really shown (keeps the first page light)
      import('qrcode').then(m => (m.default ?? m).toString(value, { type: 'svg', margin: 1, errorCorrectionLevel: 'M',
                                      color: { dark: '#0e3b2e', light: '#ffffff' } }))
        .then(svg => this.raw.set(svg))
        .catch(() => this.raw.set(''));
    });
  }
}
