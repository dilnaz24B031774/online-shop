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
}

export interface Review {
  id: number;
  username: string;
  rating: number;
  comment: string;
  created_at: string;
}

export interface ProductDetail extends Product {
  reviews: Review[];
}

export interface User {
  id: number;
  username: string;
  email: string;
  first_name: string;
  last_name: string;
  phone: string;
  role: 'customer' | 'manager' | 'admin';
  preferred_language: 'en' | 'ru' | 'kk';
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
}

export interface Order {
  id: number;
  status: 'pending' | 'paid' | 'shipped' | 'delivered' | 'cancelled';
  shipping_address: string;
  total_amount: string;
  created_at: string;
  items: OrderItem[];
  payment_method: string | null;
  payment_status: string | null;
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
