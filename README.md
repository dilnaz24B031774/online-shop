# SaudaGo — Online Shop

Our team project for the course **Basics of Information Systems**.
SaudaGo is a small online shop: customers can look at products, put them in the cart,
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
- Customer settings at `/settings`: username, first and last name, phone, display currency and password changes
- Private complaints book at `/complaints`: customers submit complaints, optionally link their own order, and see staff replies and progress
- Catalogue in 3 languages (EN / RU / KK), search by products, categories and own orders
- **Filters:** price from–to, brand, rating, only in stock; sort by price, name, rating, popularity
- Cart and checkout in one database transaction (two people cannot buy the last item)
- **Promo codes** with a percent, minimum order, dates and a usage limit
- Cancel an order: stock comes back, payment becomes refunded, promo code use comes back
- Reviews with rating 1–5 after a paid purchase: one review per product in each order
- Password recovery through linked Telegram with a one-use code, or an email link valid for one hour
- **Notifications** (bell in the header): order paid / shipped / cancelled, Black Friday
- Shop assistant chat (works without internet)
- Staff panel `/staff/`: dashboard, products, categories, orders, users
- Roles: customer, manager, admin
- Login protection: after 3 wrong tries a small math check, after 5 — block for 5 minutes

Settings are saved to the customer's account. Changing a password requires the current
password and confirmation; other sessions are signed out while the current session
receives new tokens. Currency selection applies to the catalogue, cart and orders.
Amounts are stored in USD; this study project uses fixed demonstration rates for
display (1 USD = 500 KZT / 0.92 EUR / 90 RUB), rather than live exchange rates.

## Password recovery

### Telegram

First connect Telegram in **Account settings** while you can still sign in:
enter your current shop password, open the generated bot link, and press
**Start** in Telegram. Return to settings and check that the account is linked.
A Telegram username entered as plain text is never enough to prove ownership.

Later, choose Telegram on **Forgot password?**, enter your shop username or
email, and read the six-digit code in the previously linked bot chat. Enter the
code and your new password on the website. Codes expire after ten minutes,
allow up to five incorrect attempts, and can be used once. No shop password is
sent to Telegram. A code from Telegram works even if you read it on your phone
while the local shop is open on your computer.

Create a dedicated bot with [@BotFather](https://t.me/BotFather) using `/newbot`,
as described in [Telegram's official tutorial](https://core.telegram.org/bots/tutorial#obtain-your-bot-token).
Put its credentials only in the private `.env` file:

```dotenv
TELEGRAM_BOT_TOKEN=your-bot-token
TELEGRAM_BOT_USERNAME=your_bot_username
```

Use the bot's username without `@`. Restart Django after editing `.env`, then
verify the credentials without sending a message:

```bash
python3 manage.py check_telegram
```

Keep the bot listener running in a third terminal alongside the frontend and
backend, using the same Python environment and database:

```bash
python3 manage.py run_telegram_bot
```

The listener uses [Telegram long polling](https://core.telegram.org/bots/api#getupdates),
so local development does not need a public HTTPS webhook. It accepts account
linking only in private bot chats. If the bot already has a webhook, the command
stops and leaves that webhook untouched; use a separate development bot instead.
Run only one listener for each bot token. Stop it with Ctrl+C.

### Email (optional)

Choose **Forgot password?** on `/login` and enter the email used for the account.
Open the emailed link, enter a new password twice, then sign in again. Links expire
after one hour and stop working after a successful reset. Resetting a password
also signs out existing sessions. The response is the same for registered and
unknown emails; requests are limited per source and email address.

Django automatically reads the private `.env` file in the project root. Exported
environment variables take precedence. If the file is missing, copy `.env.example`
to `.env`; install updated dependencies with `pip install -r requirements.txt`.

For **Gmail**, fill these two values in `.env`:

```dotenv
EMAIL_HOST_USER=your-address@gmail.com
EMAIL_HOST_PASSWORD=your-google-app-password
```

Enable 2-Step Verification for the sending Google account, then create an
[app password](https://myaccount.google.com/apppasswords). Use that app password,
not your normal Google password. Keep it only in `.env`, which Git ignores.
See [Google's app password instructions](https://support.google.com/accounts/answer/185833).
If Google does not offer app passwords for the account, use an SMTP provider that
supports application credentials instead.

The template already sets Gmail's `smtp.gmail.com`, port `587`, and TLS.
`DEFAULT_FROM_EMAIL` defaults to the sending Gmail address when left blank.
Check the configuration and SMTP authentication without sending an email:

```bash
python3 manage.py check_email
```

When that succeeds, **restart the backend after editing `.env`**, then request
a new recovery email for an account registered in the shop. Check the inbox
and spam folder.

Recovery reports that email is unavailable when SMTP is not configured or a
console/file/dummy backend is selected. It also reports connection,
authentication, and sending failures instead of showing a false success message.
`EMAIL_BACKEND` can override the automatic SMTP/console selection. For implicit TLS on port 465, set
`EMAIL_PORT=465`, `EMAIL_USE_SSL=true`, and `EMAIL_USE_TLS=false`.
Use the website's public HTTPS address for `FRONTEND_URL` when hosting the shop.

Each account can publish **one review per product in each paid order**. Buying
the same product in another order gives the customer another review. Buying
multiple units in one order still gives one review. Pending, failed, refunded,
and cancelled purchases do not unlock the form. Cash-on-delivery purchases
qualify once delivery and payment are confirmed. When several purchases are
available, the customer chooses the order in the product's review form.

Each new review is linked to its purchase. The API checks the buyer, product,
order and payment; a database constraint also rejects duplicate reviews for the
same purchase, including simultaneous submissions from different tabs.
Migration `0010_review_order_item` preserves existing reviews and links those
with a matching earlier paid purchase. Old reviews without a verifiable
purchase remain in the history and do not use up a later purchase.

## Database

25 tables, including `complaints` and two tables for Telegram recovery (`telegram_accounts`, `telegram_challenges`).
Full description: [`docs/DATABASE.md`](docs/DATABASE.md), ER diagram: [`docs/erd.png`](docs/erd.png),
every column and rule: [`docs/db_tables.md`](docs/db_tables.md). After changing models run `python3 manage.py db_docs`.

Rules are checked by the database itself (CHECK and UNIQUE constraints), for example:
price > 0, stock ≥ 0, rating 1–5, one review per purchased order line,
promo discount 1–90 %, promo used count not more than the limit.

## Complaints book

Customers open `/complaints` from their account, the footer, or an order's problem
link. A complaint has a subject, category, message, and optional order reference.
Each customer can read only their own complaints and can link only their own orders.

Employees use `/staff/complaints/` to search and filter complaints, reply, and change
the status from new to in progress or resolved. Resolving a complaint requires a reply.
The managed manager group receives view/change complaint permissions after migration;
other employees need those permissions explicitly. Customer messages are read-only
for employees, and complaints are not published to other shoppers.

## Promo codes

Promo codes: `WELCOME10` (−10 %), `SAUDA5` (−5 % from $20), `BLACKFRIDAY` (−25 % from $50, 20 Nov – 1 Dec).
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
| POST | `/api/products/{id}/reviews/` `{rating, comment, order_item_id}` | ✔ |
| POST | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/refresh/` | – |
| POST | `/api/auth/password-reset/` `{email}` | – |
| POST | `/api/auth/password-reset/confirm/` `{uid, token, new_password, new_password_confirm}` | – |
| POST | `/api/auth/telegram/password-reset/` `{identifier}` | – |
| POST | `/api/auth/telegram/password-reset/confirm/` `{challenge_id, code, new_password, new_password_confirm}` | – |
| GET/PATCH | `/api/me/` (profile and preferences) | ✔ |
| POST | `/api/me/password/` `{current_password, new_password, new_password_confirm}` | ✔ |
| GET | `/api/me/telegram/` (own Telegram link status) | ✔ |
| POST | `/api/me/telegram/link/`, `/api/me/telegram/unlink/` `{current_password}` | ✔ |
| GET/POST | `/api/complaints/` (own complaints only) | ✔ |
| GET | `/api/complaints/{id}/` (owner only) | ✔ |
| GET/POST | `/api/cart/` | ✔ |
| POST | `/api/promo/check/` `{code}` | ✔ |
| POST | `/api/checkout/` `{address_id, method, promo_code}` | ✔ |
| GET | `/api/orders/`, POST `/api/orders/{id}/cancel/` | ✔ |
| GET | `/api/notifications/`, POST `/api/notifications/read-all/` | ✔ |

## Tests

```bash
python3 manage.py test shop
```

Tests cover database rules, checkout transactions, passwords, refunds, promo codes,
filters, notifications, staff permissions, login protection, account settings and
private complaints.

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

