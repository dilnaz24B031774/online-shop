import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Address, AppNotification, CardInput, Cart, Category, City, Complaint, ComplaintInput, Order, Product, ProductDetail, ProductFilters,
  PromoCheck, QrInfo, Review, SavedCard, SearchResult, Tokens, TopItem, User,
} from './models';

/** The backend is reached through the same address as the website: ng serve forwards /api to Django
 *  (proxy.conf.json). So the site works the same on localhost, in Wi-Fi and through a tunnel link. */
export const API_URL = '/api';

export interface UsernameCheck {
  available: boolean;
  code?: 'length' | 'format' | 'reserved' | 'taken';
  detail?: string;
  suggestions?: string[];
}

export interface ProductQuery {
  q?: string; category?: string | number; sort?: string;
  brand?: string; min_price?: string | number; max_price?: string | number;
  min_rating?: string | number; in_stock?: string;
}

export interface LoginProof {
  challenge_id?: string;
  challenge_answer?: string;
  website?: string;
}

export interface LoginChallenge {
  id: string;
  prompt: string;
  expires_in: number;
}

export interface LoginFailure {
  code?: string;
  detail?: string;
  remaining_attempts?: number;
  challenge_required?: boolean;
  retry_after?: number;
}

export interface TelegramStatus {
  configured: boolean;
  linked: boolean;
  username: string | null;
  linked_at: string | null;
}

export interface TelegramLink {
  link_url: string;
  expires_in: number;
}

export interface TelegramResetChallenge {
  challenge_id: string;
  expires_in: number;
}

/** Every request to the backend goes through this service. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);
 
  // catalogue
  categories(): Observable<Category[]> {
    return this.http.get<Category[]>(`${API_URL}/categories/`);
  }

  products(filter: ProductQuery = {}): Observable<Product[]> {
    let params = new HttpParams();
    Object.entries(filter).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') params = params.set(k, String(v)); });
    return this.http.get<Product[]>(`${API_URL}/products/`, { params });
  }

  /** brands and price range for the filter panel */
  productFilters(category?: string): Observable<ProductFilters> {
    const params = category ? new HttpParams().set('category', category) : undefined;
    return this.http.get<ProductFilters>(`${API_URL}/products/filters/`, { params });
  }

  bestSellers(limit = 4): Observable<Product[]> {
    return this.http.get<Product[]>(`${API_URL}/products/best-sellers/`, { params: { limit } });
  }

  product(id: number): Observable<ProductDetail> {
    return this.http.get<ProductDetail>(`${API_URL}/products/${id}/`);
  }

  addReview(productId: number, rating: number, comment: string, photos: File[] = [], orderItemId?: number): Observable<Review> {
    const url = `${API_URL}/products/${productId}/reviews/`;
    if (!photos.length) {
      return this.http.post<Review>(url, { rating, comment, ...(orderItemId !== undefined ? { order_item_id: orderItemId } : {}) });
    }
    const form = new FormData();            // files go as multipart/form-data
    form.append('rating', String(rating));
    form.append('comment', comment);
    if (orderItemId !== undefined) form.append('order_item_id', String(orderItemId));
    photos.forEach(f => form.append('photos', f, f.name));
    return this.http.post<Review>(url, form);
  }

  search(q: string): Observable<SearchResult> {
    return this.http.get<SearchResult>(`${API_URL}/search/`, { params: { q } });
  }

  // accounts
  login(username: string, password: string, proof: LoginProof = {}): Observable<Tokens> {
    return this.http.post<Tokens>(`${API_URL}/auth/login/`, { username, password, ...proof });
  }

  securityChallenge(): Observable<LoginChallenge> {
    return this.http.get<LoginChallenge>(`${API_URL}/auth/challenge/`, { params: { purpose: 'login' } });
  }

  requestPasswordReset(email: string): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${API_URL}/auth/password-reset/`, { email });
  }

  telegramStatus(): Observable<TelegramStatus> {
    return this.http.get<TelegramStatus>(`${API_URL}/me/telegram/`);
  }

  linkTelegram(currentPassword: string): Observable<TelegramLink> {
    return this.http.post<TelegramLink>(`${API_URL}/me/telegram/link/`, { current_password: currentPassword });
  }

  unlinkTelegram(currentPassword: string): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${API_URL}/me/telegram/unlink/`, { current_password: currentPassword });
  }

  requestTelegramPasswordReset(identifier: string): Observable<TelegramResetChallenge> {
    return this.http.post<TelegramResetChallenge>(`${API_URL}/auth/telegram/password-reset/`, { identifier });
  }

  confirmTelegramPasswordReset(data: { challenge_id: string; code: string; new_password: string; new_password_confirm: string }): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${API_URL}/auth/telegram/password-reset/confirm/`, data);
  }

  confirmPasswordReset(data: { uid: string; token: string; new_password: string; new_password_confirm: string }): Observable<{ detail: string }> {
    return this.http.post<{ detail: string }>(`${API_URL}/auth/password-reset/confirm/`, data);
  }

  register(data: { username: string; email: string; password: string; first_name?: string }) {
    return this.http.post<{ user: User } & Tokens>(`${API_URL}/auth/register/`, data);
  }

  me(): Observable<User> {
    return this.http.get<User>(`${API_URL}/me/`);
  }

  usernameCheck(username: string): Observable<UsernameCheck> {
    return this.http.get<UsernameCheck>(`${API_URL}/auth/username-check/`, { params: { username } });
  }

  cities(): Observable<City[]> {
    return this.http.get<City[]>(`${API_URL}/cities/`);
  }

  updateMe(data: Partial<User> & { city_id?: number | null }): Observable<User> {
    return this.http.patch<User>(`${API_URL}/me/`, data);
  }

  changePassword(data: { current_password: string; new_password: string; new_password_confirm: string }): Observable<Tokens & { detail: string }> {
    return this.http.post<Tokens & { detail: string }>(`${API_URL}/me/password/`, data);
  }

  addresses(): Observable<Address[]> {
    return this.http.get<Address[]>(`${API_URL}/addresses/`);
  }

  addAddress(data: Partial<Address>): Observable<Address> {
    return this.http.post<Address>(`${API_URL}/addresses/`, data);
  }

  complaints(): Observable<Complaint[]> {
    return this.http.get<Complaint[]>(`${API_URL}/complaints/`);
  }

  createComplaint(data: ComplaintInput): Observable<Complaint> {
    return this.http.post<Complaint>(`${API_URL}/complaints/`, data);
  }

  complaint(id: number): Observable<Complaint> {
    return this.http.get<Complaint>(`${API_URL}/complaints/${id}/`);
  }

  // cart and orders
  cart(): Observable<Cart> {
    return this.http.get<Cart>(`${API_URL}/cart/`);
  }

  setCartQuantity(productId: number, quantity: number): Observable<Cart> {
    return this.http.post<Cart>(`${API_URL}/cart/`, { product_id: productId, quantity });
  }

  checkout(addressId: number, method: string, promoCode = '', card?: CardInput, installmentMonths?: number,
           saved?: { id: number; cvc: string }, saveCard = false): Observable<Order> {
    return this.http.post<Order>(`${API_URL}/checkout/`, {
      address_id: addressId, method, promo_code: promoCode, card, installment_months: installmentMonths,
      saved_card_id: saved?.id, cvc: saved?.cvc, save_card: saveCard,
    });
  }

  // ---------- saved cards (token on the server, only •••• 4242 here)
  savedCards(): Observable<{ recent_days: number; cards: SavedCard[] }> {
    return this.http.get<{ recent_days: number; cards: SavedCard[] }>(`${API_URL}/cards/`);
  }

  deleteCard(id: number): Observable<unknown> {
    return this.http.delete(`${API_URL}/cards/${id}/`);
  }

  // ---------- back in stock
  stockAlerts(): Observable<{ product_ids: number[] }> {
    return this.http.get<{ product_ids: number[] }>(`${API_URL}/stock-alerts/`);
  }

  notifyMe(productId: number): Observable<unknown> {
    return this.http.post(`${API_URL}/products/${productId}/notify-me/`, {});
  }

  cancelNotifyMe(productId: number): Observable<unknown> {
    return this.http.delete(`${API_URL}/products/${productId}/notify-me/`);
  }

  // ---------- top: hits / new / trends (real purchases only)
  top(kind: 'hits' | 'new' | 'trends', period = '30'): Observable<{ kind: string; items: TopItem[] }> {
    const params = new HttpParams().set('kind', kind).set('period', period);
    return this.http.get<{ kind: string; items: TopItem[] }>(`${API_URL}/top/`, { params });
  }

  // ---------- QR payment opened on a phone (no login: the secret token is the permission)
  qrInfo(token: string): Observable<QrInfo> {
    return this.http.get<QrInfo>(`${API_URL}/qr/${token}/`);
  }

  network(): Observable<{ lan_ip: string }> {
    return this.http.get<{ lan_ip: string }>(`${API_URL}/network/`);
  }

  qrPay(token: string): Observable<QrInfo> {
    return this.http.post<QrInfo>(`${API_URL}/qr/${token}/pay/`, {});
  }

  /** "I have paid in my bank app" */
  payQr(orderId: number): Observable<Order> {
    return this.http.post<Order>(`${API_URL}/orders/${orderId}/pay-qr/`, {});
  }

  checkPromo(code: string): Observable<PromoCheck> {
    return this.http.post<PromoCheck>(`${API_URL}/promo/check/`, { code });
  }

  notifications(): Observable<{ unread: number; items: AppNotification[] }> {
    return this.http.get<{ unread: number; items: AppNotification[] }>(`${API_URL}/notifications/`);
  }

  readNotification(id: number): Observable<unknown> {
    return this.http.post(`${API_URL}/notifications/${id}/read/`, {});
  }

  readAllNotifications(): Observable<unknown> {
    return this.http.post(`${API_URL}/notifications/read-all/`, {});
  }

  orders(): Observable<Order[]> {
    return this.http.get<Order[]>(`${API_URL}/orders/`);
  }

  assistant(message: string, lang: string): Observable<{ text: string; products: Product[]; suggestions: string[] }> {
    return this.http.post<{ text: string; products: Product[]; suggestions: string[] }>(
      `${API_URL}/assistant/`, { message, lang });
  }

  cancelOrder(id: number): Observable<Order> {
    return this.http.post<Order>(`${API_URL}/orders/${id}/cancel/`, {});
  }

   // favorites
  favorites(): Observable<Product[]> {
    return this.http.get<Product[]>(`${API_URL}/favorites/`);
  }

  addFavorite(productId: number): Observable<Product[]> {
    return this.http.post<Product[]>(`${API_URL}/favorites/`, { product_id: productId });
  }

  removeFavorite(productId: number): Observable<Product[]> {
    return this.http.delete<Product[]>(`${API_URL}/favorites/${productId}/`);
  }
}

  

