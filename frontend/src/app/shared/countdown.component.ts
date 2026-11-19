import { Component, OnDestroy, OnInit, computed, inject, input, output, signal } from '@angular/core';

import { I18nService } from '../core/i18n.service';

/** Payment timer: a ring that empties and "mm:ss" left. Emits `expired` once when the time is over. */
@Component({
  selector: 'app-countdown',
  template: `
    <div class="timer" [class.urgent]="left() <= 60" [class.over]="left() <= 0" role="timer" aria-live="polite"
         [attr.aria-label]="i.t('timer.left') + ' ' + text()">
      <svg viewBox="0 0 44 44" aria-hidden="true">
        <circle class="track" cx="22" cy="22" r="19"/>
        <circle class="bar" cx="22" cy="22" r="19" [attr.stroke-dasharray]="circle" [attr.stroke-dashoffset]="offset()"/>
      </svg>
      <div class="txt">
        <strong>{{ text() }}</strong>
        <small>{{ left() > 0 ? i.t('timer.left') : i.t('timer.over') }}</small>
      </div>
    </div>
  `,
  styles: [`
    .timer { display: inline-flex; align-items: center; gap: .7rem; }
    svg { width: 46px; height: 46px; transform: rotate(-90deg); flex: none; }
    circle { fill: none; stroke-width: 4; }
    .track { stroke: var(--line); }
    .bar { stroke: var(--green-700); stroke-linecap: round; transition: stroke-dashoffset 1s linear, stroke .3s; }
    .urgent .bar { stroke: var(--red); }
    .txt { display: flex; flex-direction: column; line-height: 1.15; }
    strong { font-size: 1.35rem; font-variant-numeric: tabular-nums; letter-spacing: .02em; color: var(--green-900); }
    .urgent strong { color: var(--red); }
    small { color: var(--muted); font-size: .78rem; }
    :host(.compact) svg { width: 30px; height: 30px; }
    :host(.compact) strong { font-size: 1rem; }
  `],
})
export class CountdownComponent implements OnInit, OnDestroy {
  readonly i = inject(I18nService);
  readonly expiresAt = input.required<string>();
  readonly totalSeconds = input(15 * 60);
  readonly expired = output<void>();

  readonly circle = 2 * Math.PI * 19;
  private readonly now = signal(Date.now());
  private timer?: ReturnType<typeof setInterval>;
  private fired = false;

  readonly left = computed(() => Math.max(0, Math.round((new Date(this.expiresAt()).getTime() - this.now()) / 1000)));
  readonly text = computed(() => {
    const s = this.left();
    const h = Math.floor(s / 3600), m = Math.floor((s % 3600) / 60), sec = s % 60;
    const mmss = `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    return h > 0 ? `${h}:${mmss}` : mmss;
  });
  readonly offset = computed(() => this.circle * (1 - Math.min(1, this.left() / this.totalSeconds())));

  ngOnInit() {
    this.timer = setInterval(() => {
      this.now.set(Date.now());
      if (this.left() <= 0 && !this.fired) {
        this.fired = true;
        this.expired.emit();
      }
    }, 1000);
  }

  ngOnDestroy() {
    clearInterval(this.timer);
  }
}
