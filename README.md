# Sauda — Online Shop

Our team project for the course **Basics of Information Systems**.
Sauda is a small online shop: customers can look at products, put them in the cart,
use a promo code and make an order. Staff work with products and orders in the admin panel.

**Stack:** Django + Django REST Framework (backend), PostgreSQL (database), Angular 19 (frontend), JWT tokens (login).

## Team

| Name | Role |
|---|---|
| Nurbergenova Inzhu | Systems Analysis & Requirements |
| Zhanabergenova Dilnaz | Data & Database |
| Nokhat Dilyara | Application & Development |
| Maralbekuly Yersaiyn | Architecture & Security |
| Oishy Ayaulym | Testing, Analytics & Integration |

## Project folders

```
config/      Django settings and main urls
shop/        models (tables), API, services, admin panel, tests
frontend/    Angular website
docs/        ERD and SQL script
```

How it works: Angular sends a request to `http://127.0.0.1:8000/api/...`,
Django checks it, works with PostgreSQL and sends back JSON.
After login the frontend gets an access token and sends it in every private request
(`Authorization: Bearer ...`). Without a token the cart and orders return `401`.

## How to run (Mac)

You need Python 3.11+, Node.js 20+ and PostgreSQL with a database called `onlineshop`.

**Terminal 1 — backend**

```bash
cd online-shop
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export POSTGRES_DB=onlineshop
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

python3 manage.py migrate
python3 manage.py seed_shop          # demo data, only the first time
python3 manage.py runserver
```

**Terminal 2 — frontend**

```bash
cd online-shop/frontend
npm install                          # only the first time
npm start
```

Website: http://localhost:4200 · Staff panel: http://127.0.0.1:8000/staff/ · Django admin: http://127.0.0.1:8000/admin/

Next time you only need `source venv/bin/activate`, the three `export` lines and `runserver`,
and `npm start` in the second terminal.

Important: if you start `runserver` without the `export` lines, Django uses an empty SQLite file
instead of PostgreSQL, and logins will not work.

## Demo accounts

Password for all: `Shop2026!`

| Username | Role |
|---|---|
| aigerim, dana, timur | customer |
| manager | store manager |
| admin | administrator |

## Features

- Registration and login with JWT tokens, password rules (min 8 chars, a digit, a capital letter)
- Catalogue in 3 languages (EN / RU / KK), search by products, categories and own orders
- **Filters:** price from–to, brand, rating, only in stock; sort by price, name, rating, popularity
- Cart and checkout in one database transaction (two people cannot buy the last item)
- **Promo codes** with a percent, minimum order, dates and a usage limit
- Cancel an order: stock comes back, payment becomes refunded, promo code use comes back
- Reviews with rating 1–5
- **Notifications** (bell in the header): order paid / shipped / cancelled, Black Friday
- Shop assistant chat (works without internet)
- Staff panel `/staff/`: dashboard, products, categories, orders, users
- Roles: customer, manager, admin
- Login protection: after 3 wrong tries a small math check, after 5 — block for 5 minutes

## Database

11 shop tables: `users`, `addresses`, `categories`, `products`, `cart_items`, `orders`,
`order_items`, `payments`, `reviews`, `notifications`, `promo_codes`
plus 2 tables for login protection. ERD: `docs/erd.mmd`.

Rules are checked by the database itself (CHECK and UNIQUE constraints), for example:
price > 0, stock ≥ 0, rating 1–5, one review per user and product,
promo discount 1–90 %, promo used count not more than the limit.

## Promo codes

Demo codes: `WELCOME10` (−10 %), `SAUDA5` (−5 % from $20), `BLACKFRIDAY` (−25 % from $50, 20 Nov – 1 Dec).
To add them to a database that already has data:

```bash
python3 manage.py seed_shop --promo-only
```

New codes can be added in Django admin → Promo codes.

## Black Friday notification

```bash
python3 manage.py send_black_friday
```

Or in Django admin: Users → select users → action "Send Black Friday notification".

## Main API

| Method | Address | Login |
|---|---|---|
| GET | `/api/products/?q=&category=&brand=&min_price=&max_price=&min_rating=&in_stock=1&sort=` | – |
| GET | `/api/products/filters/` (brands and price range) | – |
| GET | `/api/products/{id}/`, `/api/categories/`, `/api/search/?q=` | – |
| POST | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/` | – |
| GET/POST | `/api/cart/` | ✔ |
| POST | `/api/promo/check/` `{code}` | ✔ |
| POST | `/api/checkout/` `{address_id, method, promo_code}` | ✔ |
| GET | `/api/orders/`, POST `/api/orders/{id}/cancel/` | ✔ |
| GET | `/api/notifications/`, POST `/api/notifications/read-all/` | ✔ |

## Tests

```bash
python3 manage.py test shop
```

141 tests: database rules, checkout transaction, passwords, refunds, promo codes, filters,
notifications, staff panel, login protection.

## Migrations note

`main` had `0003_notification_kind_link` and `my-changes` had `0003_login_security`.
`0004_merge_login_security_notifications` joins them, so `python3 manage.py migrate`
works on both databases.

## Common problems

| Problem | What to do |
|---|---|
| "Server does not answer" on the website | backend is not running, start `runserver` again |
| `database "onlineshop" does not exist` | `CREATE DATABASE onlineshop;` in pgAdmin |
| `You have unapplied migrations` | `python3 manage.py migrate` |
| Admin login does not work | check the `export` lines; reset password: `python3 manage.py changepassword admin` |
| "Sign-in is temporarily blocked" | 5 wrong passwords — wait 5 minutes |

## Оплата, возвраты, «Топ» (Data & Database — Жанабергенова Дильназ)

| Что | Как работает | Где в базе |
|---|---|---|
| **Таймер оплаты** | QR надо оплатить за 15 минут, перевод — за 24 часа. Иначе заказ отменяется сам, товар возвращается на склад, покупатель получает уведомление. На сайте — круговой таймер. | `payments.expires_at` |
| **Возвраты** | Менеджер: Панель → Заказы → заказ → «Оформить возврат» (товар, количество, причина). Можно вернуть часть товаров. Деньги считаются с учётом скидки, товар возвращается на склад. | таблица `refunds`, `order_items.refunded_quantity`, `payments.refunded_amount` (CHECK: не больше, чем купили / оплатили) |
| **Сообщить о поступлении** | У товара с остатком 0 кнопка «Сообщить о поступлении». Когда остаток становится > 0, всем подписчикам приходит уведомление. | таблица `stock_subscriptions` (одна активная подписка на товар) |
| **Топ** | `/top`: хиты продаж (только оплаченные заказы реальных покупателей, без демо и возвратов), тренды недели (7 дней против прошлых 7), новинки. | `orders.is_demo` — демо-заказы `seed_shop` |
| **Сохранённые карты** | «Сохранить карту» → в базе только токен `tok_…`, тип и последние 4 цифры. Карты показываются, только если покупатель платил картой за последние 90 дней. Оплата сохранённой картой — с вводом CVC. | таблица `saved_cards` |
| **Промокод один раз** | Каждый покупатель может использовать код только один раз. При отмене заказа код возвращается. | таблица `promo_redemptions`, UNIQUE (user, promo) |

### QR-оплата с телефона

1. Ноутбук и телефон в одной Wi-Fi сети (если университетский Wi-Fi не пускает — включите точку доступа на телефоне и подключите к ней ноутбук).
2. Запуск для всей сети:
   ```bash
   python3 manage.py runserver 0.0.0.0:8000      # Terminal 1
   cd frontend && npm run start:lan               # Terminal 2
   ```
3. Оформите заказ с оплатой «QR в приложении банка» → отсканируйте QR камерой телефона → «Оплатить».
   Страница на ноутбуке сама станет «Оплачен», в заказе видно устройство («iPhone · Safari»).

QR содержит одноразовую секретную ссылку (`qr_payments.token`): работает один раз и только до конца таймера.

Быстрая проверка таймера: `export PAYMENT_TIMEOUT_MINUTES=1` перед `runserver`.
Отменить просроченные заказы вручную: `python3 manage.py expire_orders` (сайт и так проверяет сам).

