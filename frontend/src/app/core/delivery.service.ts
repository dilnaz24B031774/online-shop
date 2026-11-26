import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import { API_URL } from './api.service';
import type { Order } from './models';

export interface DeliveryPoint {
  lat: number;
  lng: number;
}

export type DeliveryTrackingStatus = 'unassigned' | 'awaiting_shipment' | 'awaiting_location' | 'active' | 'stale' | 'delivered' | 'cancelled';

export interface DeliveryTracking {
  order_id: number;
  order_status: Order['status'];
  shipping_address: string;
  status: DeliveryTrackingStatus;
  source: 'manual' | 'gps';
  courier: { name: string; phone: string } | null;
  position: DeliveryPoint | null;
  destination: DeliveryPoint | null;
  eta_minutes: number | null;
  updated_at: string | null;
  position_updated_at: string | null;
  position_accuracy: number | null;
}

export function isDeliveryPoint(point: DeliveryPoint | null | undefined): point is DeliveryPoint {
  return !!point && Number.isFinite(point.lat) && Number.isFinite(point.lng)
    && Math.abs(point.lat) <= 90 && Math.abs(point.lng) <= 180;
}

@Injectable({ providedIn: 'root' })
export class DeliveryService {
  private readonly http = inject(HttpClient);

  tracking(orderId: number): Observable<DeliveryTracking> {
    return this.http.get<DeliveryTracking>(`${API_URL}/orders/${orderId}/tracking/`);
  }
}
