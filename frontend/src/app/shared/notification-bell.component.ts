import { Component, ElementRef, HostListener, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { Router } from '@angular/router';

import { I18nService } from '../core/i18n.service';
import { AppNotification } from '../core/models';
import { NotificationsService } from '../core/notifications.service';

@Component({
  selector: 'app-notification-bell',
  imports: [DatePipe],
  template: `
    <button type="button" class="bell" (click)="open.set(!open())" [attr.aria-expanded]="open()"
            [attr.aria-label]="i.t('notif.open')">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 16V11a6 6 0 0 1 12 0v5l2 2H4zM10 20a2 2 0 0 0 4 0"/></svg>
      @if (n.unread() > 0) { <span class="count">{{ n.unread() > 9 ? '9+' : n.unread() }}</span> }
    </button>

    @if (open()) {
      <div class="notif-panel" role="dialog" [attr.aria-label]="i.t('notif.title')">
        <header>
          <strong>{{ i.t('notif.title') }}</strong>
          @if (n.unread() > 0) {
            <button type="button" class="link" (click)="n.markAllRead()">{{ i.t('notif.readAll') }}</button>
          }
        </header>
        <ul>
          @for (item of n.items(); track item.id) {
            <li>
              <button type="button" class="item" [class.unread]="!item.is_read" [class.promo]="item.kind === 'promo'"
                      (click)="openItem(item)">
                <span class="icon" aria-hidden="true">
                  @if (item.kind === 'promo') {
                    <svg viewBox="0 0 24 24"><path d="M3 12l9-9h8v8l-9 9zM15.5 8.5h.01"/></svg>
                  } @else {
                    <svg viewBox="0 0 24 24"><path d="M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10"/></svg>
                  }
                </span>
                <span class="text">
                  @if (item.kind === 'promo') { <b class="tag">Black Friday</b> }
                  <span>{{ textOf(item) }}</span>
                  <small>{{ item.created_at | date: 'd MMM, HH:mm' }}</small>
                </span>
                @if (!item.is_read) { <span class="dot" aria-hidden="true"></span> }
              </button>
            </li>
          } @empty {
            <li class="empty">{{ i.t('notif.empty') }}</li>
          }
        </ul>
      </div>
    }
  `,
  styles: [`
    :host { position: relative; display: block; }
    .bell {
      position: relative; width: 44px; height: 44px; border-radius: 50%; border: 0; cursor: pointer;
      background: var(--green-50); display: grid; place-items: center;
    }
    .bell svg { width: 24px; height: 24px; fill: none; stroke: var(--green-900); stroke-width: 1.8; stroke-linecap: round; stroke-linejoin: round; }
    .count {
      position: absolute; top: -4px; right: -4px; min-width: 20px; height: 20px; padding: 0 5px;
      background: var(--red); color: #fff; font-size: .72rem; font-weight: 700;
      border-radius: 999px; display: grid; place-items: center; border: 2px solid #fff;
    }
    .notif-panel {
      position: absolute; right: 0; top: 54px; width: min(380px, calc(100vw - 32px)); z-index: 60;
      background: #fff; border: 1px solid var(--line); border-radius: 14px;
      box-shadow: 0 24px 50px -24px rgba(14, 59, 46, .5); overflow: hidden;
    }
    header { display: flex; justify-content: space-between; align-items: center; padding: .85rem 1rem; border-bottom: 1px solid var(--line); }
    .link { border: 0; background: none; color: var(--green-700); font: 600 .84rem var(--font-body); cursor: pointer; }
    ul { list-style: none; margin: 0; padding: 0; max-height: 420px; overflow-y: auto; }
    .item {
      width: 100%; display: grid; grid-template-columns: 36px 1fr 10px; gap: .7rem; align-items: start;
      text-align: left; border: 0; border-bottom: 1px solid var(--line); background: #fff;
      padding: .8rem 1rem; cursor: pointer; font: inherit; color: var(--text);
    }
    .item:hover { background: var(--soft); }
    .item.unread { background: #f6fbf8; }
    .item.promo.unread { background: var(--amber-50); }
    .icon { width: 36px; height: 36px; border-radius: 50%; background: var(--green-50); display: grid; place-items: center; }
    .promo .icon { background: var(--amber); }
    .icon svg { width: 19px; height: 19px; fill: none; stroke: var(--green-900); stroke-width: 1.9; stroke-linecap: round; stroke-linejoin: round; }
    .text { display: flex; flex-direction: column; gap: .15rem; font-size: .88rem; line-height: 1.35; }
    .tag { font-size: .72rem; color: var(--green-900); background: var(--amber); align-self: flex-start; padding: .1em .5em; border-radius: 4px; }
    small { color: var(--muted); font-size: .76rem; }
    .dot { width: 9px; height: 9px; border-radius: 50%; background: var(--red); margin-top: .4rem; }
    .empty { padding: 1.4rem 1rem; color: var(--muted); font-size: .9rem; text-align: center; }
  `],
})
export class NotificationBellComponent {
  readonly i = inject(I18nService);
  readonly n = inject(NotificationsService);
  private router = inject(Router);
  private host = inject(ElementRef<HTMLElement>);
  readonly open = signal(false);

  textOf(item: AppNotification): string {
    const lang = this.i.lang();
    return (lang === 'ru' && item.message_ru) || (lang === 'kk' && item.message_kk) || item.message;
  }

  openItem(item: AppNotification) {
    this.n.markRead(item);
    if (item.link) {
      this.open.set(false);
      this.router.navigateByUrl(item.link);
    }
  }

  /** close the panel when clicking outside */
  @HostListener('document:click', ['$event'])
  onDocClick(e: MouseEvent) {
    if (this.open() && !this.host.nativeElement.contains(e.target as Node)) this.open.set(false);
  }
}
