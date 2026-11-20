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
- Customer settings at `/settings`: username, first and last name, phone, display currency and password changes
- Private complaints book at `/complaints`: customers submit complaints, optionally link their own order, and see staff replies and progress
- Catalogue in 3 languages (EN / RU / KK), search by products, categories and own orders
- **Filters:** price from–to, brand, rating, only in stock; sort by price, name, rating, popularity
- Cart and checkout in one database transaction (two people cannot buy the last item)
- **Promo codes** with a percent, minimum order, dates and a usage limit
- Cancel an order: stock comes back, payment becomes refunded, promo code use comes back
- Reviews with rating 1–5
- Password recovery by a single-use email link, valid for one hour
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

Choose **Forgot password?** on `/login` and enter the email used for the account.
Open the emailed link, enter a new password twice, then sign in again. Links expire
after one hour and stop working after a successful reset. Resetting a password
also signs out existing sessions. The response is the same for registered and
unknown emails; requests are limited per source and email address.

Locally, recovery emails appear in the **backend terminal**. To deliver email,
configure SMTP before starting Django:

```bash
export FRONTEND_URL=http://localhost:4200
export EMAIL_HOST=smtp.example.com
export EMAIL_PORT=587
export EMAIL_HOST_USER=your_smtp_username
export EMAIL_HOST_PASSWORD=your_smtp_password
export DEFAULT_FROM_EMAIL='Sauda <noreply@example.com>'
```

TLS is enabled by default for port 587. For implicit TLS on port 465, set
`EMAIL_PORT=465` and `EMAIL_USE_SSL=true`; this disables STARTTLS by default.
`EMAIL_BACKEND` can override the automatic SMTP/console selection.
Use the website's public HTTPS address for `FRONTEND_URL` when hosting the shop.

Each account can publish **one review per product**. Once published, the form
shows that the review is already submitted. Both the API and the database reject
duplicates, including simultaneous submissions from different tabs.

## Database

12 shop tables: `users`, `addresses`, `categories`, `products`, `cart_items`, `orders`,
`order_items`, `payments`, `reviews`, `notifications`, `promo_codes`, `complaints`
plus 2 tables for login protection. ERD: `docs/erd.mmd`.

Rules are checked by the database itself (CHECK and UNIQUE constraints), for example:
price > 0, stock ≥ 0, rating 1–5, one review per user and product,
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
| POST | `/api/auth/password-reset/` `{email}` | – |
| POST | `/api/auth/password-reset/confirm/` `{uid, token, new_password, new_password_confirm}` | – |
| GET/PATCH | `/api/me/` (profile and preferences) | ✔ |
| POST | `/api/me/password/` `{current_password, new_password, new_password_confirm}` | ✔ |
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
| Admin login does not work | check the `export` lines; reset password: `python3 manage.py changepassword admin` |
| "Sign-in is temporarily blocked" | 5 wrong passwords — wait 5 minutes |
