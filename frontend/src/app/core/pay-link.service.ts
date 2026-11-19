import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';

/** Builds the link inside the QR. If the site is opened as localhost, a phone cannot open "localhost",
 *  so we ask the backend for the laptop's Wi-Fi address (192.168.x.x) and use it instead. */
@Injectable({ providedIn: 'root' })
export class PayLinkService {
  private api = inject(ApiService);
  private readonly lanIp = signal<string>('');
  private asked = false;

  private get isLocal(): boolean {
    return ['localhost', '127.0.0.1', '::1', ''].includes(location.hostname);
  }

  ensure() {
    if (this.asked || !this.isLocal) return;
    this.asked = true;
    this.api.network().subscribe({ next: r => this.lanIp.set(r.lan_ip), error: () => {} });
  }

  link(token: string): string {
    const port = location.port ? `:${location.port}` : '';
    const host = this.isLocal && this.lanIp() ? this.lanIp() : location.hostname;
    return `${location.protocol}//${host}${port}/pay/${token}`;
  }

  /** true if the phone will not be able to open the link (no Wi-Fi address found) */
  localOnly(): boolean {
    return this.isLocal && !this.lanIp();
  }
}
