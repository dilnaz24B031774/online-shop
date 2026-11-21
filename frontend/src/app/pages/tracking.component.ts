import { HttpErrorResponse } from '@angular/common/http';
import { Component, DestroyRef, ViewChild, computed, effect, inject, input, signal, untracked } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { RouterLink } from '@angular/router';
import { Subscription, finalize, timeout } from 'rxjs';

import { DeliveryService, DeliveryTracking, isDeliveryPoint } from '../core/delivery.service';
import { I18nService } from '../core/i18n.service';
import { TRACKING_COPY } from '../core/tracking-copy';
import { DeliveryMapComponent } from '../shared/delivery-map.component';

@Component({
  selector: 'app-tracking',
  imports: [RouterLink, DeliveryMapComponent],
  templateUrl: './tracking.component.html',
  styleUrl: './tracking.component.scss',
})
export class TrackingComponent {
  readonly id = input.required<string>();
  readonly i = inject(I18nService);
  private readonly delivery = inject(DeliveryService);
  private readonly destroyRef = inject(DestroyRef);
  readonly copy = computed(() => TRACKING_COPY[this.i.lang()]);
  readonly tracking = signal<DeliveryTracking | null>(null);
  readonly loading = signal(true);
  readonly refreshing = signal(false);
  readonly error = signal<'connection' | 'not_found' | 'session' | null>(null);
  private readonly now = signal(Date.now());
  readonly state = computed(() => {
    const tracking = this.tracking();
    return tracking ? this.copy().states[this.stale() ? 'stale' : tracking.status] : null;
  });
  readonly stale = computed(() => {
    const tracking = this.tracking();
    if (!tracking || tracking.order_status !== 'shipped' || tracking.source !== 'gps') return false;
    if (tracking.status === 'stale') return true;
    if (!isDeliveryPoint(tracking.position)) return false;
    const reportedAt = tracking.position_updated_at ?? tracking.updated_at;
    const timestamp = reportedAt ? new Date(reportedAt).getTime() : NaN;
    return !Number.isFinite(timestamp) || this.now() - timestamp > 120_000;
  });
  readonly courierPosition = computed(() => this.tracking()?.status === 'active' && !this.stale() ? this.tracking()?.position ?? null : null);
  readonly hasCoordinates = computed(() => isDeliveryPoint(this.courierPosition()) || isDeliveryPoint(this.tracking()?.destination));
  readonly reportedAt = computed(() => this.tracking()?.position_updated_at ?? this.tracking()?.updated_at ?? null);
  readonly eta = computed(() => {
    if (this.stale()) return null;
    const minutes = this.tracking()?.eta_minutes;
    if (minutes === null || minutes === undefined || !Number.isFinite(minutes) || minutes < 0) return null;
    return minutes === 0 ? this.copy().arriving : `${minutes} ${this.copy().minutes}`;
  });
  readonly currentStep = computed(() => {
    const status = this.tracking()?.order_status;
    return status === 'delivered' ? 2 : status === 'shipped' ? 1 : 0;
  });
  readonly phoneHref = computed(() => {
    const phone = (this.tracking()?.courier?.phone ?? '').replace(/[^\d+]/g, '');
    return /^\+?\d{5,15}$/.test(phone) ? `tel:${phone}` : null;
  });
  @ViewChild(DeliveryMapComponent) map?: DeliveryMapComponent;
  private request?: Subscription;
  private timer?: ReturnType<typeof setTimeout>;
  private clock?: ReturnType<typeof setInterval>;
  private activeId = 0;
  private destroyed = false;

  constructor() {
    this.clock = setInterval(() => this.now.set(Date.now()), 15_000);
    this.destroyRef.onDestroy(() => {
      this.destroyed = true;
      clearTimeout(this.timer);
      clearInterval(this.clock);
      this.request?.unsubscribe();
    });
    effect(onCleanup => {
      const raw = this.id();
      untracked(() => {
        this.request?.unsubscribe();
        clearTimeout(this.timer);
        this.tracking.set(null);
        this.error.set(null);
        this.loading.set(true);
        const id = /^[1-9]\d*$/.test(raw) ? Number(raw) : 0;
        this.activeId = Number.isSafeInteger(id) ? id : 0;
        if (this.activeId) this.load(this.activeId);
        else { this.error.set('not_found'); this.loading.set(false); }
      });
      onCleanup(() => { this.request?.unsubscribe(); clearTimeout(this.timer); });
    });
  }

  reload() {
    if (this.activeId && !this.refreshing()) this.load(this.activeId);
  }

  date(value: string | null): string {
    if (!value) return this.copy().noUpdate;
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return this.copy().noUpdate;
    return new Intl.DateTimeFormat({ en: 'en-US', ru: 'ru-RU', kk: 'kk-KZ' }[this.i.lang()], {
      day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
    }).format(date);
  }

  stepLabel(index: number): string {
    return [this.copy().received, this.copy().onTheWay, this.copy().delivered][index];
  }

  private load(orderId: number) {
    clearTimeout(this.timer);
    this.request?.unsubscribe();
    this.refreshing.set(true);
    this.error.set(null);
    this.request = this.delivery.tracking(orderId).pipe(
      timeout(10_000),
      takeUntilDestroyed(this.destroyRef),
      finalize(() => {
        if (this.destroyed || this.activeId !== orderId) return;
        this.refreshing.set(false);
        this.loading.set(false);
        this.now.set(Date.now());
        if (this.tracking()?.order_status === 'shipped') this.timer = setTimeout(() => this.load(orderId), 15_000);
      }),
    ).subscribe({
      next: tracking => { if (this.activeId === orderId) this.tracking.set(tracking); },
      error: (error: HttpErrorResponse) => {
        if (this.activeId !== orderId) return;
        this.error.set(error.status === 404 ? 'not_found' : error.status === 401 ? 'session' : 'connection');
        if (error.status === 401 || error.status === 404) this.tracking.set(null);
      },
    });
  }
}
