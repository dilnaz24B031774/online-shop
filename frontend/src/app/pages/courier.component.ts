import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { Subscription, finalize } from 'rxjs';
import { COURIER_COPY } from '../core/courier-copy';
import { CourierService, CourierSession } from '../core/courier.service';
import { I18nService } from '../core/i18n.service';

type CourierError = 'invalid' | 'ended' | 'secure' | 'unsupported' | 'denied' | 'unavailable' | 'network';

@Component({
  selector: 'app-courier', imports: [RouterLink],
  templateUrl: './courier.component.html', styleUrl: './courier.component.scss',
})
export class CourierComponent {
  readonly i = inject(I18nService);
  readonly copy = computed(() => COURIER_COPY[this.i.lang()]);
  private readonly api = inject(CourierService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  readonly session = signal<CourierSession | null>(null);
  readonly loading = signal(true);
  readonly sharing = signal(false);
  readonly locating = signal(false);
  readonly error = signal<CourierError | ''>('');
  readonly sentAt = signal<string | null>(null);
  readonly accuracy = signal<number | null>(null);
  private token = '';
  private generation = 0;
  private timer?: ReturnType<typeof setInterval>;
  private sessionRequest?: Subscription;
  private updateRequest?: Subscription;

  constructor() {
    this.route.fragment.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(fragment => {
      this.stop();
      this.session.set(null);
      this.sentAt.set(null);
      this.accuracy.set(null);
      this.token = fragment || '';
      this.load();
    });
    this.destroyRef.onDestroy(() => this.stop());
  }

  load() {
    this.sessionRequest?.unsubscribe();
    this.error.set('');
    this.loading.set(false);
    if (!/^[A-Za-z0-9_-]{40,128}$/.test(this.token)) { this.error.set('invalid'); return; }
    this.loading.set(true);
    this.sessionRequest = this.api.session(this.token).pipe(
      takeUntilDestroyed(this.destroyRef), finalize(() => this.loading.set(false)),
    ).subscribe({ next: session => this.session.set(session), error: error => this.failure(error) });
  }

  start() {
    if (this.sharing() || !this.session()) return;
    this.error.set('');
    if (!window.isSecureContext) { this.error.set('secure'); return; }
    if (!navigator.geolocation) { this.error.set('unsupported'); return; }
    this.sharing.set(true);
    this.generation++;
    this.locate();
    if (this.sharing()) this.timer = setInterval(() => this.locate(), 15000);
  }

  stop() {
    this.sharing.set(false);
    this.locating.set(false);
    this.generation++;
    if (this.timer) clearInterval(this.timer);
    this.timer = undefined;
    this.updateRequest?.unsubscribe();
  }

  date(value: string) {
    return new Intl.DateTimeFormat({ ru: 'ru-RU', kk: 'kk-KZ', en: 'en-US' }[this.i.lang()], {
      hour: '2-digit', minute: '2-digit', second: '2-digit',
    }).format(new Date(value));
  }

  errorText() {
    const key = this.error();
    return key ? this.copy()[key] : '';
  }

  private locate() {
    if (!this.sharing() || this.locating()) return;
    this.locating.set(true);
    const generation = this.generation;
    navigator.geolocation.getCurrentPosition(position => {
      if (!this.sharing() || generation !== this.generation) return;
      this.updateRequest = this.api.locate(this.token, position).pipe(
        takeUntilDestroyed(this.destroyRef), finalize(() => this.locating.set(false)),
      ).subscribe({
        next: result => {
          this.sentAt.set(result.updated_at);
          this.accuracy.set(Math.round(position.coords.accuracy));
          this.error.set('');
        },
        error: error => this.failure(error),
      });
    }, error => {
      if (!this.sharing() || generation !== this.generation) return;
      this.locating.set(false);
      this.error.set(error.code === 1 ? 'denied' : 'unavailable');
      if (error.code === 1) this.stop();
    }, { enableHighAccuracy: true, maximumAge: 10000, timeout: 15000 });
  }

  private failure(error: HttpErrorResponse) {
    if (error.status === 403 || error.status === 410 || error.status === 404) {
      this.stop();
      this.session.set(null);
      this.error.set(error.status === 410 ? 'ended' : 'invalid');
    } else {
      this.error.set('network');
    }
  }
}
