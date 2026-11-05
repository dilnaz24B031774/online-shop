import { Component, computed, input } from '@angular/core';

/**
 * Picture for a product or category: a coloured tile with the Kazakh
 * "koshkar muiz" (ram's horn) ornament and an icon of the category.
 * We have no product photos in the database, so the category decides the look.
 */
const STYLES: Record<string, { bg: string; ink: string; icon: string }> = {
  Electronics: {
    bg: '#0E8C9B', ink: '#F5B82E',
    icon: 'M4 14v-2a8 8 0 0 1 16 0v2M4 14h3v6H5a1 1 0 0 1-1-1zM20 14h-3v6h2a1 1 0 0 0 1-1z',
  },
  Stationery: {
    bg: '#F5B82E', ink: '#1D2340',
    icon: 'M15 4l5 5L9 20H4v-5zM13 6l5 5',
  },
  Home: {
    bg: '#C2416B', ink: '#FFE3A3',
    icon: 'M8 3h8l3.5 8h-15zM12 11v8M8 21h8',
  },
  Books: {
    bg: '#3B4AA0', ink: '#8FE3EC',
    icon: 'M5 4.5A1.5 1.5 0 0 1 6.5 3H19v15H6.5A1.5 1.5 0 0 0 5 19.5zM5 19.5V4.5M9 7h6',
  },
};
const FALLBACK = { bg: '#0A6F7B', ink: '#F5B82E', icon: 'M4 7h16l-1.5 12h-13zM9 7a3 3 0 0 1 6 0' };

let uid = 0;

@Component({
  selector: 'app-category-art',
  template: `
    <svg [attr.viewBox]="'0 0 200 ' + height()" preserveAspectRatio="xMidYMid slice" role="img"
         [attr.aria-label]="category()" [style.background]="style().bg">
      <defs>
        <pattern [attr.id]="patternId" width="40" height="40" patternUnits="userSpaceOnUse"
                 [attr.patternTransform]="'rotate(' + tilt() + ')'">
          <path d="M20 34V22M20 22C20 12 8 8 6 16c-1 5 5 6 6 2M20 22c0-10 12-14 14-6 1 5-5 6-6 2"
                fill="none" [attr.stroke]="style().ink" stroke-width="2" stroke-linecap="round" opacity=".28"/>
        </pattern>
      </defs>
      <rect width="200" [attr.height]="height()" [attr.fill]="'url(#' + patternId + ')'"/>
      <circle cx="100" [attr.cy]="height() / 2" r="46" [attr.fill]="style().bg"/>
      <circle cx="100" [attr.cy]="height() / 2" r="46" fill="none" [attr.stroke]="style().ink"
              stroke-width="2.5" stroke-dasharray="4 7" opacity=".9"/>
      <g [attr.transform]="'translate(70 ' + (height() / 2 - 30) + ') scale(2.5)'">
        <path [attr.d]="style().icon" fill="none" [attr.stroke]="style().ink" stroke-width="1.6"
              stroke-linecap="round" stroke-linejoin="round"/>
      </g>
    </svg>
  `,
  styles: [`
    :host { display: block; overflow: hidden; border-radius: inherit; }
    svg { display: block; width: 100%; height: 100%; }
  `],
})
export class CategoryArtComponent {
  /** English category name, e.g. "Electronics" */
  readonly category = input<string>('');
  /** small number that slightly changes the pattern, so products differ */
  readonly seed = input<number>(0);
  readonly height = input<number>(150);

  readonly patternId = `horn-${++uid}`;
  readonly style = computed(() => STYLES[this.category()] ?? FALLBACK);
  readonly tilt = computed(() => (this.seed() * 17) % 45);
}
