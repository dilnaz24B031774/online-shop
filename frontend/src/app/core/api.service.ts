import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  AppNotification, Address, Cart, CardInput, Category, Order, Product, ProductDetail, ProductFilters, PromoCheck, Review,
  SearchResult, Tokens, User,
} from './models';

/** Address of the Django backend. Change it if the backend runs elsewhere. */
export const API_URL = 'http://127.0.0.1:8000/api';

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

  addReview(productId: number, rating: number, comment: string): Observable<Review> {
    return this.http.post<Review>(`${API_URL}/products/${productId}/reviews/`, { rating, comment });
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

  register(data: { username: string; email: string; password: string; first_name?: string }) {
    return this.http.post<{ user: User } & Tokens>(`${API_URL}/auth/register/`, data);
  }

  me(): Observable<User> {
    return this.http.get<User>(`${API_URL}/me/`);
  }

  updateMe(data: Partial<User>): Observable<User> {
    return this.http.patch<User>(`${API_URL}/me/`, data);
  }

  addresses(): Observable<Address[]> {
    return this.http.get<Address[]>(`${API_URL}/addresses/`);
  }

  addAddress(data: Partial<Address>): Observable<Address> {
    return this.http.post<Address>(`${API_URL}/addresses/`, data);
  }

  // cart and orders
  cart(): Observable<Cart> {
    return this.http.get<Cart>(`${API_URL}/cart/`);
  }

  setCartQuantity(productId: number, quantity: number): Observable<Cart> {
    return this.http.post<Cart>(`${API_URL}/cart/`, { product_id: productId, quantity });
  }

  checkout(addressId: number, method: string, promoCode = '', card?: CardInput, installmentMonths?: number): Observable<Order> {
    return this.http.post<Order>(`${API_URL}/checkout/`, {
      address_id: addressId, method, promo_code: promoCode, card, installment_months: installmentMonths,
    });
  }

  /** demo: "I have paid in my bank app" */
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

  

