# Таблицы базы данных

Файл создан командой `python manage.py db_docs` из моделей Django, поэтому совпадает с настоящими таблицами.

## cities

Cities we deliver to. The customer picks one after signing in ("Are you from Almaty?").

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `name_en` | varchar(60)  | UK | нет |
| `name_ru` | varchar(60)  |  | нет |
| `name_kk` | varchar(60)  |  | нет |
| `delivery_days_min` | smallint  |  | нет |
| `delivery_days_max` | smallint  |  | нет |
| `sort_order` | smallint  |  | нет |
| `is_active` | boolean  |  | нет |

Правила в базе:
- **CHECK** `delivery_days_min >= 1` — city_days_min_positive
- **CHECK** `delivery_days_max >= delivery_days_min` — city_days_max_not_less_min

## users

Django's user + our fields. The password column stores only a HASH

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `password` | varchar(128)  |  | нет |
| `last_login` | timestamptz  |  | да |
| `is_superuser` | boolean  |  | нет |
| `username` | varchar(150)  | UK | нет |
| `first_name` | varchar(150)  |  | нет |
| `last_name` | varchar(150)  |  | нет |
| `is_staff` | boolean  |  | нет |
| `is_active` | boolean  |  | нет |
| `date_joined` | timestamptz  |  | нет |
| `email` | varchar(254)  | UK | нет |
| `phone` | varchar(20)  |  | нет |
| `role` | varchar(20)  |  | нет |
| `preferred_language` | varchar(2)  |  | нет |
| `city_id` | bigint → cities | FK | да |

Правила в базе:
- **CHECK** `role IN ('customer', 'manager', 'admin')` — user_role_valid
- **CHECK** `preferred_language IN ('en', 'ru', 'kk')` — user_language_valid

## addresses

Address(id, user, label, city, street, apartment, postal_code, is_default)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `label` | varchar(30)  |  | нет |
| `city` | varchar(60)  |  | нет |
| `street` | varchar(150)  |  | нет |
| `apartment` | varchar(20)  |  | нет |
| `postal_code` | varchar(10)  |  | нет |
| `is_default` | boolean  |  | нет |

Правила в базе:
- **UNIQUE** (user) WHERE is_default = True — address_one_default_per_user

## categories

Category(id, name_en, name_ru, name_kk, is_active)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `name_en` | varchar(150)  |  | нет |
| `name_ru` | varchar(150)  |  | нет |
| `name_kk` | varchar(150)  |  | нет |
| `is_active` | boolean  |  | нет |

Правила в базе:
- **UNIQUE** (name_en) — category_name_en_unique

## products

Product(id, name_en, name_ru, name_kk, category, sku, description_en, description_ru, description_kk, price, stock_quantity, brand, image_url, is_active, created_at, updated_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `name_en` | varchar(150)  |  | нет |
| `name_ru` | varchar(150)  |  | нет |
| `name_kk` | varchar(150)  |  | нет |
| `category_id` | bigint → categories | FK | нет |
| `sku` | varchar(30)  | UK | нет |
| `description_en` | text  |  | нет |
| `description_ru` | text  |  | нет |
| `description_kk` | text  |  | нет |
| `price` | numeric(10,2)  |  | нет |
| `stock_quantity` | int  |  | нет |
| `brand` | varchar(60)  |  | нет |
| `image_url` | varchar(300)  |  | нет |
| `is_active` | boolean  |  | нет |
| `created_at` | timestamptz  |  | нет |
| `updated_at` | timestamptz  |  | нет |

Правила в базе:
- **CHECK** `price > 0` — product_price_positive
- **CHECK** `stock_quantity >= 0` — product_stock_not_negative
- **INDEX** (category, is_active) — product_category_active_idx

## product_images

Extra photos of a product (gallery). The main photo stays in products.image_url.

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `product_id` | bigint → products | FK | нет |
| `url` | varchar(300)  |  | нет |
| `position` | smallint  |  | нет |

Правила в базе:
- **UNIQUE** (product, position) — product_image_position_unique
- **UNIQUE** (product, url) — product_image_url_unique

## cart_items

CartItem(id, user, product, quantity, added_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `product_id` | bigint → products | FK | нет |
| `quantity` | int  |  | нет |
| `added_at` | timestamptz  |  | нет |

Правила в базе:
- **UNIQUE** (user, product) — cart_one_row_per_product
- **CHECK** `quantity > 0` — cart_quantity_positive

## promo_codes

Discount code, e.g. BLACKFRIDAY = 20 % off. Checked in services.check_promo().

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `code` | varchar(30)  | UK | нет |
| `discount_percent` | smallint  |  | нет |
| `min_order_amount` | numeric(12,2)  |  | нет |
| `valid_from` | timestamptz  |  | да |
| `valid_until` | timestamptz  |  | да |
| `max_uses` | int  |  | да |
| `used_count` | int  |  | нет |
| `is_active` | boolean  |  | нет |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **CHECK** `discount_percent >= 1 AND discount_percent <= 90` — promo_discount_1_90
- **CHECK** `min_order_amount >= 0` — promo_min_order_not_negative
- **CHECK** `max_uses IS NULL OR used_count <= max_uses` — promo_used_not_over_limit
- **CHECK** `valid_from IS NULL OR valid_until IS NULL OR valid_until > valid_from` — promo_dates_order

## orders

Order(id, user, status, shipping_address, total_amount, promo_code, discount_amount, is_demo, created_at, updated_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `status` | varchar(20)  |  | нет |
| `shipping_address` | varchar(255)  |  | нет |
| `total_amount` | numeric(12,2)  |  | нет |
| `promo_code_id` | bigint → promo_codes | FK | да |
| `discount_amount` | numeric(12,2)  |  | нет |
| `is_demo` | boolean  |  | нет |
| `created_at` | timestamptz  |  | нет |
| `updated_at` | timestamptz  |  | нет |

Правила в базе:
- **CHECK** `status IN ('pending', 'paid', 'shipped', 'delivered', 'cancelled')` — order_status_valid
- **CHECK** `total_amount >= 0` — order_total_not_negative
- **CHECK** `discount_amount >= 0` — order_discount_not_negative
- **INDEX** (status, created_at) — order_status_date_idx

## order_items

OrderItem(id, order, product, quantity, unit_price, refunded_quantity)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `order_id` | bigint → orders | FK | нет |
| `product_id` | bigint → products | FK | нет |
| `quantity` | int  |  | нет |
| `unit_price` | numeric(10,2)  |  | нет |
| `refunded_quantity` | int  |  | нет |

Правила в базе:
- **UNIQUE** (order, product) — order_item_unique_product
- **CHECK** `quantity > 0` — order_item_quantity_positive
- **CHECK** `unit_price > 0` — order_item_price_positive
- **CHECK** `refunded_quantity <= quantity` — order_item_refund_not_over_quantity

## saved_cards

SavedCard(id, user, token, brand, last4, holder, exp_month, exp_year, created_at, last_used_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `token` | varchar(40)  | UK | нет |
| `brand` | varchar(12)  |  | нет |
| `last4` | varchar(4)  |  | нет |
| `holder` | varchar(60)  |  | нет |
| `exp_month` | smallint  |  | нет |
| `exp_year` | smallint  |  | нет |
| `created_at` | timestamptz  |  | нет |
| `last_used_at` | timestamptz  |  | нет |

Правила в базе:
- **CHECK** `last4 ~ '^[0-9]{4}$'` — saved_card_last4_digits
- **CHECK** `exp_month >= 1 AND exp_month <= 12` — saved_card_month_1_12
- **UNIQUE** (user, brand, last4, exp_month, exp_year) — saved_card_once_per_user

## payments

Payment(id, order, method, amount, status, provider_reference, paid_at, card_brand, card_last4, failure_reason, installment_months, saved_card, expires_at, refunded_amount)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `order_id` | bigint → orders | FK, UK | нет |
| `method` | varchar(20)  |  | нет |
| `amount` | numeric(12,2)  |  | нет |
| `status` | varchar(20)  |  | нет |
| `provider_reference` | varchar(64)  |  | нет |
| `paid_at` | timestamptz  |  | да |
| `card_brand` | varchar(12)  |  | нет |
| `card_last4` | varchar(4)  |  | нет |
| `failure_reason` | varchar(120)  |  | нет |
| `installment_months` | smallint  |  | да |
| `saved_card_id` | bigint → saved_cards | FK | да |
| `expires_at` | timestamptz  |  | да |
| `refunded_amount` | numeric(12,2)  |  | нет |

Правила в базе:
- **CHECK** `amount > 0` — payment_amount_positive
- **CHECK** `method IN ('card', 'bank_transfer', 'cash_on_delivery', 'qr', 'installment')` — payment_method_valid
- **CHECK** `status IN ('pending', 'paid', 'failed', 'refunded')` — payment_status_valid
- **CHECK** `(NOT (status = 'paid')) OR paid_at IS NOT NULL` — payment_paid_has_time
- **CHECK** `card_last4 = '' OR card_last4 ~ '^[0-9]{4}$'` — payment_card_last4_digits
- **CHECK** `method = 'card' OR (card_last4 = '' AND card_brand = '')` — payment_card_only_for_card
- **CHECK** `(method = 'installment' AND installment_months IN (3, 6, 12, 24)) OR ((NOT (method = 'installment')) AND installment_months IS NULL)` — payment_installment_months_valid
- **CHECK** `refunded_amount >= 0 AND refunded_amount <= amount` — payment_refund_not_over_amount

## reviews

Review(id, user, product, rating, comment, created_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `product_id` | bigint → products | FK | нет |
| `rating` | smallint  |  | нет |
| `comment` | text  |  | нет |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **UNIQUE** (user, product) — review_one_per_user_product
- **CHECK** `rating >= 1 AND rating <= 5` — review_rating_1_to_5

## review_photos

Up to 3 photos in a review. The file is on disk (media/reviews/...), the table keeps its path.

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `review_id` | bigint → reviews | FK | нет |
| `image` | filefield  |  | нет |
| `position` | smallint  |  | нет |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **UNIQUE** (review, position) — review_photo_position_unique
- **CHECK** `position < 3` — review_photo_max_3

## notifications

Notification(id, user, order, kind, message, message_ru, message_kk, link, is_read, created_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `order_id` | bigint → orders | FK | да |
| `kind` | varchar(10)  |  | нет |
| `message` | varchar(255)  |  | нет |
| `message_ru` | varchar(255)  |  | нет |
| `message_kk` | varchar(255)  |  | нет |
| `link` | varchar(200)  |  | нет |
| `is_read` | boolean  |  | нет |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **CHECK** `kind IN ('order', 'promo', 'system')` — notification_kind_valid
- **INDEX** (user, is_read) — notification_user_unread_idx

## login_security_state

Expiring counters; the key is an HMAC, never an account name or IP.

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `key` | varchar(64)  | PK | нет |
| `scope` | varchar(20)  |  | нет |
| `attempts` | int  |  | нет |
| `window_started_at` | timestamptz  |  | нет |
| `locked_until` | timestamptz  |  | да |
| `updated_at` | timestamptz  |  | нет |

## login_challenges

A short-lived, single-use answer digest bound to one source and purpose.

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | varchar(64)  | PK | нет |
| `source_key` | varchar(64)  |  | нет |
| `purpose` | varchar(20)  |  | нет |
| `answer_digest` | varchar(64)  |  | нет |
| `expires_at` | timestamptz  |  | нет |
| `created_at` | timestamptz  |  | нет |

## favorites

Favorite(id, user, product, created_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `product_id` | bigint → products | FK | нет |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **UNIQUE** (user, product) — favorite_one_per_user_product

## refunds

Refund(id, order, order_item, quantity, amount, reason, comment, created_by, created_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `order_id` | bigint → orders | FK | нет |
| `order_item_id` | bigint → order_items | FK | нет |
| `quantity` | int  |  | нет |
| `amount` | numeric(12,2)  |  | нет |
| `reason` | varchar(20)  |  | нет |
| `comment` | varchar(200)  |  | нет |
| `created_by_id` | bigint → users | FK | да |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **CHECK** `quantity > 0` — refund_quantity_positive
- **CHECK** `amount > 0` — refund_amount_positive
- **CHECK** `reason IN ('defect', 'wrong_item', 'changed_mind', 'other')` — refund_reason_valid

## stock_subscriptions

StockSubscription(id, user, product, created_at, notified_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `product_id` | bigint → products | FK | нет |
| `created_at` | timestamptz  |  | нет |
| `notified_at` | timestamptz  |  | да |

Правила в базе:
- **UNIQUE** (user, product) WHERE notified_at IS NULL — stock_subscription_one_active

## promo_redemptions

PromoRedemption(id, user, promo, order, created_at)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `user_id` | bigint → users | FK | нет |
| `promo_id` | bigint → promo_codes | FK | нет |
| `order_id` | bigint → orders | FK, UK | нет |
| `created_at` | timestamptz  |  | нет |

Правила в базе:
- **UNIQUE** (user, promo) — promo_once_per_user

## qr_payments

QrPayment(id, payment, token, created_at, expires_at, paid_at, paid_device)

| Колонка | Тип | Ключ | Пусто? |
|---|---|---|---|
| `id` | bigint  | PK | нет |
| `payment_id` | bigint → payments | FK, UK | нет |
| `token` | varchar(64)  | UK | нет |
| `created_at` | timestamptz  |  | нет |
| `expires_at` | timestamptz  |  | нет |
| `paid_at` | timestamptz  |  | да |
| `paid_device` | varchar(80)  |  | нет |

Правила в базе:
- **CHECK** `expires_at > created_at` — qr_expires_after_created
- **CHECK** `paid_at IS NULL OR (NOT (paid_device = ''))` — qr_paid_has_device
