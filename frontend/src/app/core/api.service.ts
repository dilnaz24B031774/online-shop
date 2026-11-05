import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';

import {
  Address, Cart, Category, Order, Product, ProductDetail, Review, SearchResult, Tokens, User,
} from './models';

/** Address of the Django backend. Change it if the backend runs elsewhere. */
export const API_URL = 'http://127.0.0.1:8000/api';

/** Every request to the backend goes through this service. */
@Injectable({ providedIn: 'root' })
export class ApiService {
  private http = inject(HttpClient);

  // catalogue
  categories(): Observable<Category[]> {
    return this.http.get<Category[]>(`${API_URL}/categories/`);
  }

  products(filter: { q?: string; category?: string | number; sort?: string } = {}): Observable<Product[]> {
    let params = new HttpParams();
    Object.entries(filter).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') params = params.set(k, String(v)); });
    return this.http.get<Product[]>(`${API_URL}/products/`, { params });
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
  login(username: string, password: string): Observable<Tokens> {
    return this.http.post<Tokens>(`${API_URL}/auth/login/`, { username, password });
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

  checkout(addressId: number, method: string): Observable<Order> {
    return this.http.post<Order>(`${API_URL}/checkout/`, { address_id: addressId, method });
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
}
