import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { computed, signal } from '@angular/core';
import { provideRouter } from '@angular/router';

import { API_URL } from '../app/core/api.service';
import { AuthService } from '../app/core/auth.service';
import { Complaint } from '../app/core/models';
import { ThemeService } from '../app/core/theme.service';
import { SupportComponent } from '../app/pages/support.component';

describe('Appearance preferences', () => {
  beforeEach(() => localStorage.clear());
  afterEach(() => {
    localStorage.clear();
    document.documentElement.removeAttribute('data-theme');
    document.documentElement.removeAttribute('data-accent');
  });

  it('uses light and forest when saved preferences are invalid', () => {
    localStorage.setItem('sauda.theme', 'broken');
    localStorage.setItem('sauda.accent', 'unknown');
    const theme = TestBed.inject(ThemeService);
    expect(theme.theme()).toBe('light');
    expect(theme.accent()).toBe('green');
    expect(document.documentElement.getAttribute('data-theme')).toBe('light');
  });

  it('restores both appearance and accent after the service is recreated', () => {
    const first = TestBed.inject(ThemeService);
    first.use('dark');
    first.useAccent('blue');
    TestBed.resetTestingModule();
    const restored = TestBed.inject(ThemeService);
    expect(restored.theme()).toBe('dark');
    expect(restored.accent()).toBe('blue');
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark');
    expect(document.documentElement.getAttribute('data-accent')).toBe('blue');
  });

  it('applies a preference even when browser storage is unavailable', () => {
    const theme = TestBed.inject(ThemeService);
    spyOn(Storage.prototype, 'setItem').and.throwError('Storage unavailable');
    expect(() => { theme.use('dark'); theme.useAccent('violet'); }).not.toThrow();
    expect(theme.theme()).toBe('dark');
    expect(document.documentElement.getAttribute('data-accent')).toBe('violet');
  });
});

const TICKET: Complaint = {
  id: 17, order: null, category: 'service', subject: 'Private account question',
  message: 'Please help me update my account details.', status: 'in_progress',
  staff_response: 'You can update your profile in Settings.', replied_at: '2026-11-22T10:00:00Z',
  created_at: '2026-11-22T09:00:00Z', updated_at: '2026-11-22T10:00:00Z',
};

describe('SupportComponent', () => {
  let token: ReturnType<typeof signal<string | null>>;
  let http: HttpTestingController;
  let fixture: ComponentFixture<SupportComponent>;

  beforeEach(() => {
    localStorage.clear();
    token = signal<string | null>(null);
    TestBed.configureTestingModule({ providers: [
      provideRouter([]), provideHttpClient(), provideHttpClientTesting(),
      { provide: AuthService, useValue: { token, isLoggedIn: computed(() => !!token()) } },
    ] });
    http = TestBed.inject(HttpTestingController);
  });
  afterEach(() => { http.verify(); localStorage.clear(); });

  function render(access: string | null = null) {
    token.set(access);
    fixture = TestBed.createComponent(SupportComponent);
    fixture.detectChanges();
    return fixture.componentInstance;
  }

  function loadTickets(items: Complaint[] = []) {
    http.expectOne(`${API_URL}/complaints/`).flush(items);
    http.expectOne(`${API_URL}/orders/`).flush([]);
    fixture.detectChanges();
  }

  it('shows searchable help to guests without requesting private tickets or orders', () => {
    const component = render();
    http.expectNone(`${API_URL}/complaints/`);
    http.expectNone(`${API_URL}/orders/`);
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelectorAll('.faq-card').length).toBe(6);
    expect(element.querySelector('a[href*="/login"]')).not.toBeNull();
    expect(element.querySelector('form')).toBeNull();
    component.query.set('password');
    fixture.detectChanges();
    expect(element.querySelectorAll('.faq-card').length).toBe(1);
  });

  it('renders the customer’s ticket status and staff reply', () => {
    const component = render('customer-token');
    loadTickets([TICKET]);
    component.toggle(TICKET.id);
    fixture.detectChanges();
    const element = fixture.nativeElement as HTMLElement;
    expect(element.querySelector('.ticket-toggle')?.textContent).toContain(TICKET.subject);
    expect(element.querySelector('.status-in_progress')).not.toBeNull();
    expect(element.querySelector('.staff-response')?.textContent).toContain(TICKET.staff_response);
  });

  it('sends a trimmed request to the real complaint API and displays the returned ticket', () => {
    const component = render('customer-token');
    loadTickets();
    component.form = { subject: '  Private account question  ', message: '  Please help me update my account details.  ', category: 'service', order: null };
    component.submit();
    const request = http.expectOne(`${API_URL}/complaints/`);
    expect(request.request.method).toBe('POST');
    expect(request.request.body).toEqual({ subject: TICKET.subject, message: TICKET.message, category: 'service', order: null });
    request.flush(TICKET);
    fixture.detectChanges();
    expect(component.sentId()).toBe(TICKET.id);
    expect(component.items()).toEqual([TICKET]);
    expect(component.form.message).toBe('');
    expect(component.busy()).toBeFalse();
  });

  it('rejects an order that is not in the customer’s order list', () => {
    const component = render('customer-token');
    loadTickets();
    component.form = { subject: 'Order question', message: 'Please check the delivery for this order.', category: 'delivery', order: 999 };
    component.submit();
    expect(component.errors()['order']).toBeTruthy();
    http.expectNone(request => request.method === 'POST');
  });

  it('cancels private requests and hides personal content when the customer signs out', () => {
    const component = render('customer-token');
    const tickets = http.expectOne(`${API_URL}/complaints/`);
    const orders = http.expectOne(`${API_URL}/orders/`);
    token.set(null);
    fixture.detectChanges();
    expect(tickets.cancelled).toBeTrue();
    expect(orders.cancelled).toBeTrue();
    expect(component.items()).toEqual([]);
    expect((fixture.nativeElement as HTMLElement).querySelector('.history')).toBeNull();
  });

  it('clears the previous customer’s tickets before loading another session', () => {
    const component = render('first-customer');
    loadTickets([TICKET]);
    token.set('second-customer');
    fixture.detectChanges();
    expect(component.items()).toEqual([]);
    expect((fixture.nativeElement as HTMLElement).textContent).not.toContain(TICKET.subject);
    loadTickets();
    expect(component.items()).toEqual([]);
  });
});
