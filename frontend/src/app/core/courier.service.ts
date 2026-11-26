import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { API_URL } from './api.service';

export interface CourierSession {
  order_id: number;
  courier_name: string;
  order_status: string;
  expires_at: string;
}

@Injectable({ providedIn: 'root' })
export class CourierService {
  private readonly http = inject(HttpClient);

  session(token: string) {
    return this.http.post<CourierSession>(`${API_URL}/courier/session/`, { token });
  }

  locate(token: string, position: GeolocationPosition) {
    return this.http.post<{ updated_at: string }>(`${API_URL}/courier/location/`, {
      token,
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy,
    });
  }
}
