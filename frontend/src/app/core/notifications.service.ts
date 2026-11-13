import { Injectable, effect, inject, signal } from '@angular/core';

import { ApiService } from './api.service';
import { AuthService } from './auth.service';
import { AppNotification } from './models';

/**
 * Notifications for the bell in the header.
 * Loads them after login and checks for new ones every 30 seconds,
 * so a Black Friday message appears without reloading the page.
 */
@Injectable({ providedIn: 'root' })
export class NotificationsService {
  private api = inject(ApiService);
  private auth = inject(AuthService);
  private timer: ReturnType<typeof setInterval> | null = null;

  readonly items = signal<AppNotification[]>([]);
  readonly unread = signal(0);

  constructor() {
    effect(() => {
      if (this.auth.isLoggedIn()) {
        this.load();
        this.timer ??= setInterval(() => this.load(), 30_000);
      } else {
        if (this.timer) clearInterval(this.timer);
        this.timer = null;
        this.items.set([]);
        this.unread.set(0);
      }
    });
  }

  load() {
    this.api.notifications().subscribe({
      next: r => { this.items.set(r.items); this.unread.set(r.unread); },
      error: () => {},
    });
  }

  markRead(n: AppNotification) {
    if (n.is_read) return;
    this.items.update(list => list.map(x => (x.id === n.id ? { ...x, is_read: true } : x)));
    this.unread.update(u => Math.max(0, u - 1));
    this.api.readNotification(n.id).subscribe({ error: () => this.load() });
  }

  markAllRead() {
    this.items.update(list => list.map(x => ({ ...x, is_read: true })));
    this.unread.set(0);
    this.api.readAllNotifications().subscribe({ error: () => this.load() });
  }
}
