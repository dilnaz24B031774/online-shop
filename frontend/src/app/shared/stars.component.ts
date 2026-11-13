import { Component, computed, input } from '@angular/core';
import { DecimalPipe } from '@angular/common';

@Component({
  selector: 'app-stars',
  template: `
    <span class="stars" [attr.aria-label]="(value() ?? 0) + ' / 5'">
      @for (s of five; track s) {
        <svg viewBox="0 0 20 20" [class.on]="s <= rounded()"><path d="M10 1.8l2.5 5.3 5.8.7-4.3 4 1.1 5.8L10 14.8l-5.1 2.8 1.1-5.8-4.3-4 5.8-.7z"/></svg>
      }
      @if (count() !== null && count() !== undefined) { <span class="count">{{ value() ? (value()! | number: '1.1-1') : '–' }} ({{ count() }})</span> }
    </span>
  `,
  imports: [DecimalPipe],
  styles: [`
    .stars { display: inline-flex; align-items: center; gap: 2px; }
    svg { width: 15px; height: 15px; fill: #d6e4ea; }
    svg.on { fill: #F5B82E; }
    .count { margin-left: 6px; font-size: .85rem; color: var(--ink-soft); }
  `],
})
export class StarsComponent {
  readonly value = input<number | null>(null);
  readonly count = input<number | null>(null);
  readonly five = [1, 2, 3, 4, 5];
  readonly rounded = computed(() => Math.round(this.value() ?? 0));
}
