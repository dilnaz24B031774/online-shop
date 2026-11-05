# Sauda — Online Shop

Student project · Basics of Information Systems

```
onlineshop/            Django + PostgreSQL: database, REST API, JWT login, admin panel
onlineshop/frontend/   Angular 19: the website customers use
```

## How the parts talk to each other (integration)

```
 Angular (browser, port 4200)  ──HTTP + JSON──▶  Django REST API (port 8000)  ──▶  PostgreSQL
        frontend/src/app/core/api.service.ts        shop/api.py                     shop/models.py
```

1. The customer clicks something on the website (Angular).
2. Angular sends a request to `http://127.0.0.1:8000/api/...` (all requests are in `api.service.ts`).
3. Django checks the request, works with the database and answers with JSON.
4. Angular shows the answer.

**Login with tokens (JWT):** `POST /api/auth/login/` returns an `access` token.
Angular saves it and adds `Authorization: Bearer <token>` to every private request
(`auth.interceptor.ts`). Without a token, cart and orders answer `401`.

## API

| Method | Address | What it does | Login |
|---|---|---|---|
| GET | /api/categories/ | categories with product count | – |
| GET | /api/products/?q=&category=&sort= | catalogue, filter, sort | – |
| GET | /api/products/best-sellers/ | top 4 products | – |
| GET | /api/products/{id}/ | one product with reviews | – |
| POST | /api/products/{id}/reviews/ | write a review (rating 1–5) | ✔ |
| GET | /api/search/?q= | search products, categories, own orders | – |
| POST | /api/auth/register/ | create account (password rules checked) | – |
| POST | /api/auth/login/ | username + password → JWT tokens | – |
| POST | /api/auth/refresh/ | new access token | – |
| GET/PATCH | /api/me/ | my profile | ✔ |
| GET/POST | /api/addresses/ | my addresses | ✔ |
| GET/POST | /api/cart/ | my cart / set quantity | ✔ |
| POST | /api/checkout/ | place order (one transaction) | ✔ |
| GET | /api/orders/ | my orders | ✔ |
| POST | /api/orders/{id}/cancel/ | cancel order + refund, stock goes back | ✔ |
| POST | /api/assistant/ | shop assistant: {message, lang} → text + products | – |

## Run it on a Mac

You need: **Python 3.11+**, **Node.js 20+** (nodejs.org, LTS), **PostgreSQL** with the database `onlineshop`.

### Terminal 1 — backend

```bash
cd ~/Downloads/onlineshop
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

export POSTGRES_DB=onlineshop
export POSTGRES_USER=postgres
export POSTGRES_PASSWORD=your_password

python3 manage.py migrate
python3 manage.py seed_shop        # demo data: 59 products, 9 categories (only the first time)
python3 manage.py runserver
```

Leave this window open. Check: http://127.0.0.1:8000/api/products/ shows JSON.

### Terminal 2 — frontend (open a NEW terminal window: Cmd+N)

```bash
cd ~/Downloads/onlineshop/frontend
npm install                        # only the first time, takes 1–2 minutes
npm start
```

Open **http://localhost:4200** — this is the website.

### Every next time

Terminal 1: `cd ~/Downloads/onlineshop`, `source venv/bin/activate`, the three `export` lines, `python3 manage.py runserver`.
Terminal 2: `cd ~/Downloads/onlineshop/frontend`, `npm start`.

## New: refunds, assistant, descriptions

- **Cancel + refund.** "My orders" → *Cancel order* (until the order is shipped). One transaction: the order becomes
  *cancelled*, the payment *refunded*, the products go back to stock, the customer gets a notification.
  Staff can also do it in the admin panel: Orders → select → action *Cancel and refund selected orders*.
- **Shop assistant.** The chat button at the bottom right. It works without internet and without external AI:
  it understands keywords in EN/RU/KK, answers about delivery, payment, refunds, contacts and the last order,
  and finds products with a budget ("наушники до 150$", "gift ideas", "кроссовка 120$ дейін"). Code: `shop/assistant.py`.
- **Descriptions** in English, Russian and Kazakh for all products. To add them to an existing database
  without deleting anything: `python3 manage.py fill_descriptions`.

## Product photos

Photos and mock product data come from [DummyJSON](https://dummyjson.com) (free demo data for online shops).
The link to each photo is saved in the database (`products.image_url`, can be changed in the admin panel).

- **Online:** photos load from the internet automatically.
- **Offline (for the exam):** with the backend running, run once in Terminal 2:
  ```bash
  cd frontend
  npm run download-images
  ```
  Photos are saved in `frontend/public/products/`. Restart `npm start` — the shop now works without internet.
- Products without a photo show a clean icon instead.

## Updating from the previous version

The database got two new product fields (brand, photo) and a bigger demo catalogue:

```bash
python3 manage.py migrate
python3 manage.py seed_shop --reset     # recreates demo products, orders and demo users
```

`--reset` deletes all shop data (products, orders, carts) and the demo users, then creates them again.
Users you added yourself stay, but their orders are deleted.

## Demo accounts (password for all: `Shop2026!`)

| Username | Role | Where |
|---|---|---|
| aigerim, dana, timur | customer | website |
| manager | store manager | website + admin panel |
| admin | administrator | http://127.0.0.1:8000/admin |

## What to show

| Exam requirement | Where |
|---|---|
| More than 5 functions | registration, login (JWT), catalogue, search, cart, checkout, orders, cancel + refund, reviews, addresses, notifications, AI assistant |
| Multilanguage | EN / RU / ҚАЗ switch in the header — interface and product names change |
| Search (2–3 entities) | search box in the header: products, categories, your orders |
| Admin panel | http://127.0.0.1:8000/admin — CRUD for all tables, roles |

## Tests

```bash
python3 manage.py test shop      # 31 tests: rules, transactions, passwords, refunds, assistant, API flow
```

## Problems

| Message | What to do |
|---|---|
| "The server does not answer…" on the website | Terminal 1 is closed or `runserver` stopped — start it again |
| `database "onlineshop" does not exist` | create it in pgAdmin / DataGrip: `CREATE DATABASE onlineshop;` |
| `npm: command not found` | install Node.js LTS from nodejs.org |
| Users added in the admin are not in pgAdmin | `runserver` was started without the `export` lines (it used SQLite) |
