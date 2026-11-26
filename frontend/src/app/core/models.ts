import type { CurrencyCode } from './currency.service';

// Types that match the JSON from the Django REST API (shop/serializers.py)

export interface Category {
  id: number;
  name_en: string;
  name_ru: string;
  name_kk: string;
  product_count?: number;
}

export interface Product {
  id: number;
  sku: string;
  name_en: string;
  name_ru: string;
  name_kk: string;
  description_en: string;
  description_ru: string;
  description_kk: string;
  price: string;
  stock_quantity: number;
  brand: string;
  image_url: string;
  category: Category;
  avg_rating: number | null;
  review_count: number;
  created_at?: string;
}

export interface Review {
  id: number;
  user_id: number;
  username: string;
  rating: number;
  comment: string;
  created_at: string;
  author?: string;     // "Aigerim K."
  photos?: string[];   // /media/reviews/... , up to 3
}

export interface ReviewPurchase {
  order_item_id: number;
  order_id: number;
  purchased_at: string;
}

export interface ReviewEligibility {
  can_review: boolean;
  remaining_purchases: number;
  reason: 'login_required' | 'purchase_required' | 'review_exists' | null;
  purchases: ReviewPurchase[];
}

export interface ProductDetail extends Product {
  reviews: Review[];
  images?: string[];   // main photo first, then the gallery
  review_eligibility: ReviewEligibility;
}

export interface User {
  id: number;
  customer_number?: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: 'customer' | 'manager' | 'admin';
  preferred_language: 'en' | 'ru' | 'kk';
  preferred_currency: CurrencyCode;
  city?: City | null;
}

export interface City {
  id: number;
  name_en: string;
  name_ru: string;
  name_kk: string;
  delivery_days_min: number;
  delivery_days_max: number;
}

export interface Address {
  id: number;
  label: string;
  city: string;
  street: string;
  apartment: string;
  postal_code: string;
  is_default: boolean;
}

export interface CartItem {
  id: number;
  product: Product;
  quantity: number;
  line_total: string;
}

export interface Cart {
  items: CartItem[];
  total: string;
  count: number;
}

export interface OrderItem {
  id: number;
  product: Product;
  quantity: number;
  unit_price: string;
  line_total: string;
  refunded_quantity?: number;
}

export interface Order {
  id: number;
  status: 'pending' | 'paid' | 'shipped' | 'delivered' | 'cancelled';
  shipping_address: string;
  total_amount: string;
  discount_amount: string;
  promo: string | null;
  created_at: string;
  items: OrderItem[];
  payment_method: string | null;
  payment_status: string | null;
  card_brand?: string;
  card_last4?: string;
  installment_months?: number | null;
  expires_at?: string | null;          // QR / transfer: pay before this moment
  refunded_amount?: string;
  failure_reason?: string;
  refunds?: Refund[];
  qr_token?: string | null;            // only for my own unpaid QR order
  qr_paid_device?: string;
}

export interface QrInfo {
  order_id: number;
  amount: string;
  shop: string;
  items: number;
  state: 'pending' | 'paid' | 'expired' | 'cancelled' | 'not_found';
  expires_at: string;
  created_at: string;
  paid_at: string | null;
  paid_device: string;
}

export interface Refund {
  id: number;
  product_id: number;
  name_en: string;
  name_ru: string;
  name_kk: string;
  quantity: number;
  amount: string;
  reason: string;
  created_at: string;
}

/** a saved card: only type, last 4 digits and expiry ever reach the browser */
export interface SavedCard {
  id: number;
  brand: string;
  last4: string;
  holder: string;
  exp_month: number;
  exp_year: number;
  last_used_at: string;
}

export interface TopItem {
  product: Product;
  units?: number;
  prev_units?: number;
  growth?: number | null;              // null = first sales this week
}

/** typed by the customer, sent once to /checkout/, never saved in the browser */
export interface CardInput {
  number: string;
  holder: string;
  exp_month: number;
  exp_year: number;
  cvc: string;
}

export interface SearchResult {
  products: Product[];
  categories: Category[];
  orders: Order[];
}

export interface Tokens {
  access: string;
  refresh: string;
}

export interface AppNotification {
  id: number;
  kind: 'order' | 'promo' | 'system';
  message: string;
  message_ru: string;
  message_kk: string;
  link: string;
  order: number | null;
  is_read: boolean;
  created_at: string;
}

export interface ProductFilters {
  min_price: string;
  max_price: string;
  brands: { brand: string; count: number }[];
}

export interface PromoCheck {
  valid: boolean;
  code: string;
  percent: number;
  subtotal: string;
  discount: string;
  total: string;
}


export type ComplaintCategory = 'product' | 'delivery' | 'payment' | 'service' | 'other';
export type ComplaintStatus = 'new' | 'in_progress' | 'resolved';

export interface Complaint {
  id: number;
  order: number | null;
  category: ComplaintCategory;
  subject: string;
  message: string;
  status: ComplaintStatus;
  staff_response: string;
  replied_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface ComplaintInput {
  order: number | null;
  category: ComplaintCategory;
  subject: string;
  message: string;
}
