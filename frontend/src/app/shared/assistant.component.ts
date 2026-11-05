import { Component, ElementRef, inject, signal, viewChild } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Product } from '../core/models';
import { ProductImageComponent } from './product-image.component';

interface ChatMessage {
  from: 'bot' | 'me';
  text: string;
  products?: Product[];
}

/** Floating chat with the simple shop assistant (backend: shop/assistant.py). */
@Component({
  selector: 'app-assistant',
  imports: [FormsModule, RouterLink, ProductImageComponent],
  template: `
    @if (open()) {
      <section class="panel-chat" role="dialog" [attr.aria-label]="i.t('chat.title')">
        <header>
          <span class="bot-avatar" aria-hidden="true">
            <svg viewBox="0 0 24 24"><rect x="4" y="7" width="16" height="12" rx="4"/><path d="M12 3v4M9 13h.01M15 13h.01M9.5 16h5"/></svg>
          </span>
          <div class="title">
            <strong>{{ i.t('chat.title') }}</strong>
            <small>{{ i.t('chat.subtitle') }}</small>
          </div>
          <button type="button" class="close" (click)="open.set(false)" [attr.aria-label]="i.t('chat.close')">×</button>
        </header>

        <div class="messages" #list aria-live="polite">
          @for (m of messages(); track $index) {
            <div class="msg" [class.me]="m.from === 'me'">
              <p>{{ m.text }}</p>
              @if (m.products?.length) {
                <div class="found">
                  @for (p of m.products; track p.id) {
                    <a class="item" [routerLink]="['/product', p.id]">
                      <span class="thumb"><app-product-image [product]="p" /></span>
                      <span class="name">{{ i.pick(p) }}</span>
                      <strong>\${{ p.price }}</strong>
                    </a>
                  }
                </div>
              }
            </div>
          }
          @if (busy()) { <div class="msg typing"><span></span><span></span><span></span></div> }
        </div>

        @if (suggestions().length) {
          <div class="chips">
            @for (s of suggestions(); track s) {
              <button type="button" (click)="send(s)">{{ s }}</button>
            }
          </div>
        }

        <form class="input" (ngSubmit)="send(text)">
          <input name="text" [(ngModel)]="text" [placeholder]="i.t('chat.placeholder')" autocomplete="off" maxlength="300" />
          <button type="submit" [disabled]="busy() || !text.trim()" [attr.aria-label]="i.t('chat.send')">
            <svg viewBox="0 0 24 24"><path d="M4 12l16-8-6 16-2-7z"/></svg>
          </button>
        </form>
      </section>
    }

    <button type="button" class="fab" (click)="toggle()" [attr.aria-expanded]="open()">
      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5h16v11H9l-5 4z"/><path d="M8 10h.01M12 10h.01M16 10h.01"/></svg>
      <span>{{ i.t('chat.open') }}</span>
    </button>
  `,
  styles: [`
    :host { position: fixed; right: 20px; bottom: 20px; z-index: 50; display: flex; flex-direction: column; align-items: flex-end; gap: 12px; }
    .fab {
      display: inline-flex; align-items: center; gap: .55rem; border: 0; cursor: pointer;
      background: var(--green-700); color: #fff; font: 600 .92rem var(--font-body);
      padding: .8rem 1.15rem; border-radius: 999px; box-shadow: 0 12px 28px -12px rgba(14, 59, 46, .7);
    }
    .fab:hover { background: var(--green-900); }
    .fab svg { width: 22px; height: 22px; fill: none; stroke: var(--amber); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }

    .panel-chat {
      width: min(380px, calc(100vw - 40px)); height: min(560px, calc(100vh - 120px));
      background: #fff; border-radius: 18px; border: 1px solid var(--line);
      box-shadow: 0 24px 60px -24px rgba(14, 59, 46, .55); display: flex; flex-direction: column; overflow: hidden;
    }
    header { display: flex; align-items: center; gap: .7rem; padding: .9rem 1rem; background: var(--green-900); color: #fff; }
    .bot-avatar { width: 38px; height: 38px; border-radius: 50%; background: var(--amber); display: grid; place-items: center; flex: none; }
    .bot-avatar svg { width: 22px; height: 22px; fill: none; stroke: var(--green-900); stroke-width: 2; stroke-linecap: round; stroke-linejoin: round; }
    .title { display: flex; flex-direction: column; line-height: 1.2; flex: 1; }
    .title small { color: #b9d2c6; font-size: .78rem; }
    .close { border: 0; background: transparent; color: #fff; font-size: 1.6rem; line-height: 1; cursor: pointer; padding: 0 .2rem; }

    .messages { flex: 1; overflow-y: auto; padding: 1rem; display: flex; flex-direction: column; gap: .7rem; background: var(--soft); }
    .msg { max-width: 88%; align-self: flex-start; background: #fff; border: 1px solid var(--line); border-radius: 14px 14px 14px 4px; padding: .6rem .8rem; }
    .msg p { margin: 0; font-size: .9rem; }
    .msg.me { align-self: flex-end; background: var(--green-700); border-color: var(--green-700); color: #fff; border-radius: 14px 14px 4px 14px; }
    .found { display: flex; flex-direction: column; gap: .4rem; margin-top: .6rem; }
    .item {
      display: grid; grid-template-columns: 44px 1fr auto; gap: .6rem; align-items: center;
      padding: .35rem; border-radius: 10px; color: var(--text); text-decoration: none !important; background: var(--soft);
    }
    .item:hover { background: var(--green-50); }
    .thumb { width: 44px; height: 44px; border-radius: 8px; background: #fff; padding: 3px; display: block; }
    .name { font-size: .84rem; line-height: 1.25; }
    .item strong { font-size: .86rem; color: var(--green-900); }
    .typing { display: flex; gap: 4px; padding: .8rem; }
    .typing span { width: 7px; height: 7px; border-radius: 50%; background: var(--muted); opacity: .5; animation: blink 1s infinite; }
    .typing span:nth-child(2) { animation-delay: .2s; } .typing span:nth-child(3) { animation-delay: .4s; }
    @keyframes blink { 50% { opacity: 1; } }

    .chips { display: flex; gap: 6px; overflow-x: auto; padding: .6rem 1rem; border-top: 1px solid var(--line); scrollbar-width: none; }
    .chips button {
      flex: none; border: 1px solid var(--line); background: #fff; color: var(--green-700); cursor: pointer;
      font: 600 .8rem var(--font-body); padding: .4em .85em; border-radius: 999px; white-space: nowrap;
    }
    .chips button:hover { border-color: var(--green-700); }
    .input { display: flex; gap: .5rem; padding: .7rem 1rem 1rem; }
    .input input { border-radius: 999px; padding: .65em 1em; }
    .input button {
      flex: none; width: 44px; height: 44px; border-radius: 50%; border: 0; background: var(--amber); cursor: pointer;
      display: grid; place-items: center;
    }
    .input button[disabled] { opacity: .45; cursor: default; }
    .input svg { width: 20px; height: 20px; fill: var(--green-900); }

    @media (max-width: 560px) {
      :host { right: 12px; bottom: 12px; }
      .fab span { display: none; }
      .fab { padding: .9rem; }
    }
  `],
})
export class AssistantComponent {
  readonly i = inject(I18nService);
  private api = inject(ApiService);
  private list = viewChild<ElementRef<HTMLElement>>('list');

  readonly open = signal(false);
  readonly busy = signal(false);
  readonly messages = signal<ChatMessage[]>([]);
  readonly suggestions = signal<string[]>([]);
  text = '';

  toggle() {
    this.open.update(v => !v);
    if (this.open() && this.messages().length === 0) this.ask('');   // greeting
  }

  send(message: string) {
    const m = message.trim();
    if (!m || this.busy()) return;
    this.messages.update(list => [...list, { from: 'me', text: m }]);
    this.text = '';
    this.ask(m);
  }

  private ask(message: string) {
    this.busy.set(true);
    this.scroll();
    this.api.assistant(message, this.i.lang()).subscribe({
      next: r => {
        this.messages.update(list => [...list, { from: 'bot', text: r.text, products: r.products }]);
        this.suggestions.set(r.suggestions);
        this.busy.set(false);
        this.scroll();
      },
      error: () => {
        this.messages.update(list => [...list, { from: 'bot', text: this.i.t('common.error') }]);
        this.busy.set(false);
      },
    });
  }

  private scroll() {
    setTimeout(() => {
      const el = this.list()?.nativeElement;
      if (el) el.scrollTop = el.scrollHeight;
    });
  }
}
