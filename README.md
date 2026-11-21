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

**Once: database settings in `.env`**

```bash
cd online-shop
cp .env.example .env                 # Windows: copy .env.example .env
```

Open `.env` and write your database name, user and password. The file stays on your computer
(it is in `.gitignore`), so every teammate has their own. No more `export` lines.

**Terminal 1 — backend**

```bash
cd online-shop
python3 -m venv venv
source venv/bin/activate             # Windows: venv\Scripts\activate
pip install -r requirements.txt

python3 manage.py migrate
python3 manage.py seed_shop          # demo data, only the first time (also loads the catalogue)
python3 manage.py load_catalog       # database that already has data: adds new products and photos
python3 manage.py runserver
```

**Terminal 2 — frontend**

```bash
cd online-shop/frontend
npm install                          # only the first time
npm start
```

Website: http://localhost:4200 · Staff panel: http://127.0.0.1:8000/staff/ · Django admin: http://127.0.0.1:8000/admin/

Next time you only need `source venv/bin/activate` and `runserver`, and `npm start` in the second terminal.

If `.env` is missing, Django stops with the message "PostgreSQL is not configured" instead of
silently opening an empty SQLite file. For a quick run without PostgreSQL write `USE_SQLITE=1` in `.env`.

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

20 tables. Full description: [`docs/DATABASE.md`](docs/DATABASE.md), ER diagram: [`docs/erd.png`](docs/erd.png),
every column and rule: [`docs/db_tables.md`](docs/db_tables.md). After changing models run `python3 manage.py db_docs`.

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
| `PostgreSQL is not configured` | create `.env` from `.env.example` (see "How to run") |
| Admin login does not work | check `.env`; reset password: `python3 manage.py changepassword admin` |
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

Сайт обращается к бэкенду через тот же адрес (`/api`, см. `frontend/proxy.conf.json`), поэтому наружу нужно открыть только сайт.

**Вариант 1. Одна сеть (Wi-Fi или режим модема на телефоне) — работает даже без интернета:**
```bash
python3 manage.py runserver                    # Terminal 1
cd frontend && npm run start:lan               # Terminal 2
```
Под QR видно, на какой адрес он ведёт. После смены сети нажмите «Обновить адрес».

**Вариант 2. Из любой сети, в том числе с 5G (туннель):**
```bash
brew install cloudflared                       # один раз (Windows: winget install Cloudflare.cloudflared)
cd frontend && npm run tunnel                  # Terminal 3, сайт и бэкенд уже запущены
```
Откройте на ноутбуке ссылку `https://….trycloudflare.com` из вывода команды, и QR поведёт на неё.

Оформите заказ с оплатой по QR → отсканируйте QR камерой телефона → «Оплатить».
Страница на ноутбуке сама станет «Оплачен», в заказе видно устройство («iPhone · Safari»).

QR содержит одноразовую секретную ссылку (`qr_payments.token`): работает один раз и только до конца таймера.

Быстрая проверка таймера: `export PAYMENT_TIMEOUT_MINUTES=1` перед `runserver`.
Отменить просроченные заказы вручную: `python3 manage.py expire_orders` (сайт и так проверяет сам).

## Регион, резервные копии, фото в отзывах

| Что | Как работает | Таблицы |
|---|---|---|
| **Город** | после входа окно «Вы из города Алматы?» → «Да» или выбор из 18 городов; город в шапке, срок доставки на странице товара, город подставляется в новый адрес | `cities`, `users.city_id` |
| **Резервные копии** | `python3 manage.py backup_db` (pg_dump → `backups/`, хранятся последние 10), `backup_db --list`, `restore_db ИМЯ --yes` (перед восстановлением сохраняет текущее состояние). В панели админа: «Резервные копии» → создать и скачать | все таблицы |
| **Фото в отзывах** | до 3 фото, только JPG, PNG или WEBP (тип проверяется по содержимому файла), до 5 МБ; просмотр по клику | `review_photos` (позиции 0–2, CHECK → не больше 3) |
| **Новые категории** | «Часы», «Украшения», «Мебель», «Аксессуары для телефона», «Авто и мото» — `python3 manage.py load_catalog` | `categories`, `products` |

Фото из отзывов лежат в папке `media/`, копии базы — в `backups/`. Обе папки не попадают в git.

