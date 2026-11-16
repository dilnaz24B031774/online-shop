import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { HttpErrorResponse } from '@angular/common/http';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { finalize, Subscription } from 'rxjs';

import { ApiService } from '../core/api.service';
import { I18nService } from '../core/i18n.service';
import { Complaint, ComplaintCategory, ComplaintInput, Order } from '../core/models';

type Errors = Record<string, string>;

@Component({
  selector: 'app-complaints',
  imports: [FormsModule, RouterLink],
  templateUrl: './complaints.component.html',
  styleUrl: './complaints.component.scss',
})
export class ComplaintsComponent implements OnInit {
  readonly i = inject(I18nService);
  private readonly api = inject(ApiService);
  private readonly route = inject(ActivatedRoute);
  private readonly destroyRef = inject(DestroyRef);
  readonly categories: ComplaintCategory[] = ['product', 'delivery', 'payment', 'service', 'other'];
  readonly items = signal<Complaint[]>([]);
  readonly orders = signal<Order[]>([]);
  readonly loading = signal(true);
  readonly loadError = signal(false);
  readonly ordersLoading = signal(true);
  readonly ordersError = signal(false);
  readonly orderUnavailable = signal(false);
  readonly busy = signal(false);
  readonly errors = signal<Errors>({});
  readonly sentId = signal<number | null>(null);
  readonly expanded = signal<number | null>(null);
  form: ComplaintInput = { subject: '', message: '', category: 'other', order: null };
  private listRequest?: Subscription;
  private ordersRequest?: Subscription;
  private queryOrder: number | null = null;
  private orderEdited = false;

  ngOnInit() {
    this.route.queryParamMap.pipe(takeUntilDestroyed(this.destroyRef)).subscribe(params => {
      const raw = params.get('order');
      this.queryOrder = raw && /^[1-9]\d*$/.test(raw) && Number.isSafeInteger(Number(raw)) ? Number(raw) : null;
      this.orderEdited = false;
      this.applyQueryOrder();
    });
    this.loadComplaints();
    this.loadOrders();
  }

  loadComplaints() {
    this.listRequest?.unsubscribe();
    this.loading.set(true);
    this.loadError.set(false);
    this.listRequest = this.api.complaints().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: items => { this.items.set(items); this.loading.set(false); },
      error: () => { this.loadError.set(true); this.loading.set(false); },
    });
  }

  loadOrders() {
    this.ordersRequest?.unsubscribe();
    this.ordersLoading.set(true);
    this.ordersError.set(false);
    this.ordersRequest = this.api.orders().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: orders => { this.orders.set(orders); this.ordersLoading.set(false); this.applyQueryOrder(); },
      error: () => { this.ordersError.set(true); this.ordersLoading.set(false); },
    });
  }

  selectOrder() {
    this.orderEdited = true;
    this.orderUnavailable.set(false);
    this.edited('order');
  }

  edited(field: string) {
    this.sentId.set(null);
    const errors = { ...this.errors() };
    delete errors[field];
    delete errors['form'];
    this.errors.set(errors);
  }

  toggle(id: number) {
    this.expanded.update(current => current === id ? null : id);
  }

  submit() {
    if (this.busy()) return;
    const data: ComplaintInput = { ...this.form, subject: this.form.subject.trim(), message: this.form.message.trim() };
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
    this.api.createComplaint(data).pipe(takeUntilDestroyed(this.destroyRef), finalize(() => this.busy.set(false))).subscribe({
      next: complaint => {
        this.listRequest?.unsubscribe();
        this.items.update(items => [complaint, ...items.filter(item => item.id !== complaint.id)]);
        this.expanded.set(complaint.id);
        this.sentId.set(complaint.id);
        this.form = { subject: '', message: '', category: 'other', order: null };
        this.orderEdited = true;
        this.orderUnavailable.set(false);
        this.loadComplaints();
      },
      error: error => this.errors.set(this.errorMessages(error)),
    });
  }

  date(value: string): string {
    const date = new Date(value);
    if (!Number.isFinite(date.getTime())) return '';
    return new Intl.DateTimeFormat({ en: 'en-US', ru: 'ru-RU', kk: 'kk-KZ' }[this.i.lang()], {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
    }).format(date);
  }

  private applyQueryOrder() {
    if (this.ordersLoading() || this.orderEdited) return;
    const order = this.orders().find(order => order.id === this.queryOrder);
    this.form.order = order?.id ?? null;
    this.orderUnavailable.set(this.queryOrder !== null && !order);
  }

  private errorMessages(error: HttpErrorResponse): Errors {
    if (error.status === 401) return { form: this.i.t('settings.sessionExpired') };
    if (!error.status || error.status >= 500) return { form: this.i.t('complaints.sendError') };
    const body: unknown = error.error;
    if (!body || typeof body !== 'object' || Array.isArray(body)) return { form: this.i.t('complaints.sendError') };
    const errors: Errors = {};
    for (const field of Object.keys(body)) {
      const key: Record<string, string> = {
        subject: 'complaints.subjectInvalid', message: 'complaints.messageLength',
        category: 'complaints.categoryInvalid', order: 'complaints.orderInvalid',
      };
      errors[key[field] ? field : 'form'] = this.i.t(key[field] || 'complaints.sendError');
    }
    return Object.keys(errors).length ? errors : { form: this.i.t('complaints.sendError') };
  }
}
