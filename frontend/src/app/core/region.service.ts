import { Injectable, computed, effect, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { City } from './models';

const GUEST_KEY = 'sauda_city';
const ASKED_KEY = 'sauda_city_asked';

function read(key: string, store: Storage | undefined): string | null {
  try { return store?.getItem(key) ?? null; } catch { return null; }
}
function write(key: string, value: string | null, store: Storage | undefined) {
  try { value === null ? store?.removeItem(key) : store?.setItem(key, value); } catch { /* private mode */ }
}

/** The customer's city: saved in users.city for a signed-in customer, in the browser for a guest.
 *  After signing in, a customer without a city sees the question "Are you from Almaty?". */
@Injectable({ providedIn: 'root' })
export class RegionService {
  private api = inject(ApiService);
  private auth = inject(AuthService);

  readonly cities = signal<City[]>([]);
  readonly open = signal(false);
  readonly showList = signal(false);   // false = "Are you from Almaty?", true = list of cities
  readonly saving = signal(false);
  private readonly guestCityId = signal<number | null>(Number(read(GUEST_KEY, globalThis.localStorage)) || null);
  private loaded = false;

  /** The city we suggest first: Almaty, the biggest city */
  readonly suggested = computed(() => this.cities().find(c => c.name_en === 'Almaty') ?? this.cities()[0] ?? null);

  readonly current = computed<City | null>(() => {
    const user = this.auth.user();
    if (user) return user.city ?? null;
    return this.cities().find(c => c.id === this.guestCityId()) ?? null;
  });

  constructor() {
    // signed in and no city yet -> ask once per browser session
    effect(() => {
      const user = this.auth.user();
      if (user && !user.city && !read(ASKED_KEY, globalThis.sessionStorage)) {
        this.load();
        this.showList.set(false);
        this.open.set(true);
      }
    });
  }

  load() {
    if (this.loaded) return;
    this.loaded = true;
    this.api.cities().subscribe({ next: c => this.cities.set(c), error: () => (this.loaded = false) });
  }

  /** "Change city" in the header: open the list straight away */
  ask() {
    this.load();
    this.showList.set(true);
    this.open.set(true);
  }

  close() {
    write(ASKED_KEY, '1', globalThis.sessionStorage);
    this.open.set(false);
  }

  choose(city: City) {
    write(ASKED_KEY, '1', globalThis.sessionStorage);
    if (!this.auth.user()) {
      this.guestCityId.set(city.id);
      write(GUEST_KEY, String(city.id), globalThis.localStorage);
      this.open.set(false);
      return;
    }
    this.saving.set(true);
    this.api.updateMe({ city_id: city.id }).subscribe({
      next: u => { this.auth.user.set(u); this.saving.set(false); this.open.set(false); },
      error: () => this.saving.set(false),
    });
  }
}
