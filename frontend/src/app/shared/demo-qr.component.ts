import { Component, computed, input } from '@angular/core';

/** A QR-looking picture for the demo. It is NOT a real payment QR code. */
@Component({
  selector: 'app-demo-qr',
  template: `
    <svg [attr.viewBox]="'0 0 ' + size + ' ' + size" role="img" [attr.aria-label]="label()">
      <rect [attr.width]="size" [attr.height]="size" fill="#fff"/>
      @for (c of cells(); track $index) { <rect [attr.x]="c[0]" [attr.y]="c[1]" width="1" height="1" fill="#0e3b2e"/> }
      @for (f of finders; track $index) {
        <rect [attr.x]="f[0]" [attr.y]="f[1]" width="7" height="7" fill="#0e3b2e"/>
        <rect [attr.x]="f[0] + 1" [attr.y]="f[1] + 1" width="5" height="5" fill="#fff"/>
        <rect [attr.x]="f[0] + 2" [attr.y]="f[1] + 2" width="3" height="3" fill="#0e3b2e"/>
      }
    </svg>
  `,
  styles: [`:host { display: block; width: 190px; padding: 12px; background: #fff; border-radius: 14px; border: 1px solid var(--line); }
            svg { display: block; width: 100%; shape-rendering: crispEdges; }`],
})
export class DemoQrComponent {
  readonly seed = input(1);
  readonly label = input('QR');
  readonly size = 25;
  readonly finders = [[0, 0], [18, 0], [0, 18]];

  readonly cells = computed(() => {
    let x = this.seed() * 9301 + 49297;
    const rnd = () => (x = (x * 1103515245 + 12345) % 2147483648) / 2147483648;
    const out: number[][] = [];
    for (let r = 0; r < this.size; r++) {
      for (let c = 0; c < this.size; c++) {
        const inFinder = (r < 8 && c < 8) || (r < 8 && c > 16) || (r > 16 && c < 8);
        if (!inFinder && rnd() > 0.52) out.push([c, r]);
      }
    }
    return out;
  });
}
