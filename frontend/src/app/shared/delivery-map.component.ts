import { AfterViewInit, Component, ElementRef, OnDestroy, ViewChild, computed, effect, inject, input, signal } from '@angular/core';
import type { Map as LeafletMap, Marker, TileLayer } from 'leaflet';

import { DeliveryPoint, isDeliveryPoint } from '../core/delivery.service';
import { I18nService } from '../core/i18n.service';
import { TRACKING_COPY } from '../core/tracking-copy';

type Leaflet = typeof import('leaflet');

@Component({
  selector: 'app-delivery-map',
  template: `
    <div #canvas class="map-canvas" role="region" [attr.aria-label]="copy().mapLabel"></div>
    @if (loading()) { <div class="map-notice" role="status">{{ copy().mapLoading }}</div> }
    @if (failed()) {
      <div class="map-notice map-error" role="status">
        <p>{{ copy().mapError }}</p>
        <button type="button" (click)="retry()">{{ copy().mapRetry }}</button>
      </div>
    }
  `,
  styles: [`
    :host { position: relative; display: block; height: 100%; min-height: 360px; isolation: isolate; }
    .map-canvas { width: 100%; height: 100%; min-height: 360px; background: var(--soft); }
    .map-notice { position: absolute; z-index: 1100; inset: 50% auto auto 50%; transform: translate(-50%, -50%);
      width: min(330px, calc(100% - 36px)); padding: 1rem 1.2rem; border-radius: 12px; text-align: center;
      background: var(--surface); color: var(--text); border: 1px solid var(--line); box-shadow: var(--shadow); font-size: .9rem; }
    .map-notice p { margin-bottom: .65rem; }
    .map-notice button { border: 0; border-radius: 8px; padding: .5rem .8rem; font: inherit; font-weight: 600;
      cursor: pointer; background: var(--green-700); color: #fff; }
    @media (max-width: 640px) { :host, .map-canvas { min-height: 330px; } }
  `],
})
export class DeliveryMapComponent implements AfterViewInit, OnDestroy {
  readonly position = input<DeliveryPoint | null>(null);
  readonly destination = input<DeliveryPoint | null>(null);
  readonly courierName = input('');
  private readonly i = inject(I18nService);
  readonly copy = computed(() => TRACKING_COPY[this.i.lang()]);
  readonly loading = signal(true);
  readonly failed = signal(false);
  @ViewChild('canvas', { static: true }) private canvas!: ElementRef<HTMLDivElement>;
  private map?: LeafletMap;
  private tiles?: TileLayer;
  private leaflet?: Leaflet;
  private courierMarker?: Marker;
  private destinationMarker?: Marker;
  private destroyed = false;
  private fitted = false;

  constructor() {
    effect(() => {
      const position = this.position();
      const destination = this.destination();
      const name = this.courierName();
      const copy = this.copy();
      if (this.map && this.leaflet) this.updateMarkers(position, destination, name, copy.courier, copy.destination);
    });
  }

  async ngAfterViewInit() {
    try {
      const leaflet = await import('leaflet');
      if (this.destroyed) return;
      this.leaflet = leaflet;
      this.map = leaflet.map(this.canvas.nativeElement, { scrollWheelZoom: false, zoomControl: true });
      this.tiles = leaflet.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
      });
      this.tiles.on('tileerror', () => this.failed.set(true));
      this.tiles.on('tileload', () => this.failed.set(false));
      this.tiles.addTo(this.map);
      const copy = this.copy();
      this.updateMarkers(this.position(), this.destination(), this.courierName(), copy.courier, copy.destination);
      this.loading.set(false);
    } catch {
      this.loading.set(false);
      this.failed.set(true);
    }
  }

  ngOnDestroy() {
    this.destroyed = true;
    this.map?.remove();
  }

  recenter() {
    if (!this.map || !this.leaflet) return;
    const points = [this.position(), this.destination()].filter(isDeliveryPoint);
    if (!points.length) return;
    this.map.invalidateSize();
    if (points.length === 1) this.map.setView([points[0].lat, points[0].lng], 15, { animate: false });
    else this.map.fitBounds(this.leaflet.latLngBounds(points.map(point => [point.lat, point.lng])), { padding: [54, 54], maxZoom: 16, animate: false });
    this.fitted = true;
  }

  retry() {
    this.failed.set(false);
    if (!this.map) {
      void this.ngAfterViewInit();
      return;
    }
    this.tiles?.redraw();
    this.recenter();
  }

  private updateMarkers(position: DeliveryPoint | null, destination: DeliveryPoint | null, name: string, courierLabel: string, destinationLabel: string) {
    if (!this.map || !this.leaflet) return;
    this.courierMarker?.remove();
    this.destinationMarker?.remove();
    this.courierMarker = undefined;
    this.destinationMarker = undefined;
    if (isDeliveryPoint(position)) {
      this.courierMarker = this.leaflet.marker([position.lat, position.lng], {
        icon: this.icon('courier'), title: name ? `${courierLabel}: ${name}` : courierLabel,
      }).addTo(this.map);
    }
    if (isDeliveryPoint(destination)) {
      this.destinationMarker = this.leaflet.marker([destination.lat, destination.lng], {
        icon: this.icon('destination'), title: destinationLabel,
      }).addTo(this.map);
    }
    if (!this.fitted) this.recenter();
  }

  private icon(kind: 'courier' | 'destination') {
    const courier = kind === 'courier';
    const svg = courier
      ? '<path d="M3 6h11v11H3zM14 10h4l3 3v4h-7M7 19a2 2 0 1 0 0-.01M17 19a2 2 0 1 0 0-.01"/>'
      : '<path d="M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z"/><circle cx="12" cy="10" r="2.5"/>';
    return this.leaflet!.divIcon({
      className: '', iconSize: [46, 46], iconAnchor: [23, 23],
      html: `<span style="display:grid;place-items:center;width:46px;height:46px;border:3px solid white;border-radius:50%;background:${courier ? '#155a45' : '#f6a623'};color:${courier ? '#fff' : '#163c2e'};box-shadow:0 3px 12px #163c2e44"><svg viewBox="0 0 24 24" width="25" height="25" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${svg}</svg></span>`,
    });
  }
}
