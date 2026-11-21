import { Injectable, inject, signal } from '@angular/core';

import { ApiService } from './api.service';

/** Where the QR link leads:
 *  public — a tunnel or hosting link (https://….trycloudflare.com): opens from any network, also 5G;
 *  lan    — the laptop's address in the local network (Wi-Fi or phone hotspot): the phone must be in it;
 *  local  — only "localhost" is known: a phone cannot open it. */
export type LinkKind = 'public' | 'lan' | 'local';

const PRIVATE = /^(10\.|192\.168\.|172\.(1[6-9]|2\d|3[01])\.|169\.254\.)/;

@Injectable({ providedIn: 'root' })
export class PayLinkService {
  private api = inject(ApiService);
  private readonly lanIp = signal<string>('');
  readonly checking = signal(false);
  private asked = false;

  private get isLocal(): boolean {
    return ['localhost', '127.0.0.1', '::1', ''].includes(location.hostname);
  }

  /** Ask the backend once for the laptop's address in the network (only needed on localhost). */
  ensure() {
    if (this.asked || !this.isLocal) return;
    this.asked = true;
    this.refresh();
  }

  /** Ask again, e.g. after switching to another Wi-Fi or to the phone hotspot. */
  refresh() {
    if (!this.isLocal) return;
    this.checking.set(true);
    this.api.network().subscribe({
      next: r => { this.lanIp.set(r.lan_ip); this.checking.set(false); },
      error: () => this.checking.set(false),
    });
  }

  canRefresh(): boolean {
    return this.isLocal;
  }

  host(): string {
    const port = location.port ? `:${location.port}` : '';
    return (this.isLocal && this.lanIp() ? this.lanIp() : location.hostname) + port;
  }

  link(token: string): string {
    return `${location.protocol}//${this.host()}/pay/${token}`;
  }

  kind(): LinkKind {
    if (this.isLocal) return this.lanIp() ? 'lan' : 'local';
    return PRIVATE.test(location.hostname) ? 'lan' : 'public';
  }

  /** true if the phone will not be able to open the link */
  localOnly(): boolean {
    return this.kind() === 'local';
  }
}
