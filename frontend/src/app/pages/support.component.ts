import { Component, DestroyRef, computed, effect, inject, signal, untracked } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { Subscription } from 'rxjs';

import { ApiService } from '../core/api.service';
import { AuthService } from '../core/auth.service';
import { I18nService } from '../core/i18n.service';
import { Complaint, ComplaintCategory, ComplaintInput, Order } from '../core/models';
import { SupportTopic, supportCopy } from '../core/support-copy';

type Errors = Record<string, string>;

@Component({
  selector: 'app-support',
  imports: [FormsModule, RouterLink],
  templateUrl: './support.component.html',
  styleUrl: './support.component.scss',
})
export class SupportComponent {
  readonly i = inject(I18nService);
  readonly auth = inject(AuthService);
  private readonly api = inject(ApiService);
  private readonly destroyRef = inject(DestroyRef);
  readonly copy = computed(() => supportCopy(this.i.lang()));
  readonly topics: SupportTopic[] = ['all', 'account', 'payment', 'delivery'];
  /** quick ways to get help, shown as a row of cards under the hero */
  readonly quick = computed(() => ({
    en: { write: ['Write to us', 'Answer in your account'], track: ['Track my order', 'Courier on the map'],
          call: ['Call us', '+7 700 000 00 00'], mail: ['Email', 'hello@sauda.kz'] },
    ru: { write: ['Написать нам', 'Ответ придёт в аккаунт'], track: ['Где мой заказ', 'Курьер на карте'],
          call: ['Позвонить', '+7 700 000 00 00'], mail: ['Почта', 'hello@sauda.kz'] },
    kk: { write: ['Бізге жазу', 'Жауап аккаунтқа келеді'], track: ['Тапсырысым қайда', 'Курьер картада'],
          call: ['Қоңырау шалу', '+7 700 000 00 00'], mail: ['Пошта', 'hello@sauda.kz'] },
  }[this.i.lang()]));
  readonly topic = signal<SupportTopic>('all');
  readonly query = signal('');
  readonly faqs = computed(() => {
    const query = this.query().trim().toLocaleLowerCase();
    return this.copy().faqs.filter(faq => (this.topic() === 'all' || faq.topic === this.topic()) &&
      (!query || `${faq.question} ${faq.answer}`.toLocaleLowerCase().includes(query)));
  });
  readonly categories: ComplaintCategory[] = ['service', 'product', 'delivery', 'payment', 'other'];
  readonly items = signal<Complaint[]>([]);
  readonly orders = signal<Order[]>([]);
  readonly loading = signal(false);
  readonly loadError = signal(false);
  readonly ordersLoading = signal(false);
  readonly ordersError = signal(false);
  readonly busy = signal(false);
  readonly errors = signal<Errors>({});
  readonly sentId = signal<number | null>(null);
  readonly expanded = signal<number | null>(null);
  form: ComplaintInput = this.emptyForm();
  private listRequest?: Subscription;
  private ordersRequest?: Subscription;
  private sendRequest?: Subscription;
  private activeToken: string | null = null;

  constructor() {
    // Clear private content immediately when the account changes; cancel old responses.
    effect(() => {
      const token = this.auth.token();
      if (token === this.activeToken) return;
      this.activeToken = token;
      untracked(() => {
        this.resetPrivate();
        if (token) { this.loadTickets(); this.loadOrders(); }
      });
    });
  }

  clearSearch() { this.query.set(''); this.topic.set('all'); }

  loadTickets() {
    if (!this.auth.isLoggedIn()) return;
    this.listRequest?.unsubscribe();
    this.loading.set(true);
    this.loadError.set(false);
    this.listRequest = this.api.complaints().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: items => { this.items.set(items); this.loading.set(false); },
      error: () => { this.loadError.set(true); this.loading.set(false); },
    });
  }

  loadOrders() {
    if (!this.auth.isLoggedIn()) return;
    this.ordersRequest?.unsubscribe();
    this.ordersLoading.set(true);
    this.ordersError.set(false);
    this.ordersRequest = this.api.orders().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: orders => { this.orders.set(orders); this.ordersLoading.set(false); },
      error: () => { this.ordersError.set(true); this.ordersLoading.set(false); },
    });
  }

  edited(field: string) {
    const errors = { ...this.errors() };
    delete errors[field];
    delete errors['form'];
    this.errors.set(errors);
    this.sentId.set(null);
  }

  submit() {
    if (this.busy() || !this.auth.isLoggedIn()) return;
    const data = { ...this.form, subject: this.form.subject.trim(), message: this.form.message.trim() };
    const errors: Errors = {};
    if (!data.subject) errors['subject'] = this.i.t('complaints.subjectRequired');
    else if (data.subject.length > 150) errors['subject'] = this.i.t('complaints.subjectLong');
    if (data.message.length < 10 || data.message.length > 5000) errors['message'] = this.i.t('complaints.messageLength');
    if (!this.categories.includes(data.category)) errors['category'] = this.i.t('complaints.categoryInvalid');
    if (data.order !== null && !this.orders().some(order => order.id === data.order)) errors['order'] = this.i.t('complaints.orderInvalid');
    this.errors.set(errors);
    this.sentId.set(null);
    if (Object.keys(errors).length) return;
    this.busy.set(true);
    this.sendRequest = this.api.createComplaint(data).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: item => {
        this.listRequest?.unsubscribe();
        this.loading.set(false);
        this.loadError.set(false);
        this.items.update(items => [item, ...items.filter(old => old.id !== item.id)]);
        this.sentId.set(item.id);
        this.expanded.set(item.id);
        this.form = this.emptyForm();
        this.busy.set(false);
      },
      error: error => { this.errors.set(this.errorMessages(error)); this.busy.set(false); },
    });
  }

  toggle(id: number) { this.expanded.update(current => current === id ? null : id); }

  date(value: string): string {
    const date = new Date(value);
    return Number.isFinite(date.getTime()) ? new Intl.DateTimeFormat({ en: 'en-US', ru: 'ru-RU', kk: 'kk-KZ' }[this.i.lang()],
      { day: 'numeric', month: 'short', year: 'numeric' }).format(date) : '';
  }

  private resetPrivate() {
    this.listRequest?.unsubscribe();
    this.ordersRequest?.unsubscribe();
    this.sendRequest?.unsubscribe();
    this.items.set([]);
    this.orders.set([]);
    this.form = this.emptyForm();
    this.loading.set(false);
    this.loadError.set(false);
    this.ordersLoading.set(false);
    this.ordersError.set(false);
    this.busy.set(false);
    this.errors.set({});
    this.sentId.set(null);
    this.expanded.set(null);
  }

  private emptyForm(): ComplaintInput { return { subject: '', message: '', category: 'service', order: null }; }

  private errorMessages(error: HttpErrorResponse): Errors {
    if (error.status === 401) return { form: this.i.t('settings.sessionExpired') };
    if (!error.status || error.status >= 500 || !error.error || typeof error.error !== 'object') return { form: this.i.t('complaints.sendError') };
    const keys: Record<string, string> = {
      subject: 'complaints.subjectInvalid', message: 'complaints.messageLength',
      category: 'complaints.categoryInvalid', order: 'complaints.orderInvalid',
    };
    const errors: Errors = {};
    for (const field of Object.keys(error.error)) errors[keys[field] ? field : 'form'] = this.i.t(keys[field] || 'complaints.sendError');
    return Object.keys(errors).length ? errors : { form: this.i.t('complaints.sendError') };
  }
}
