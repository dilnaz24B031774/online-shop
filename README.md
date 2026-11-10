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

## Панель администратора

Откройте **http://127.0.0.1:8000/staff/** и войдите под учётной записью
администратора. На сайте ссылка «Админ-панель» также ведёт в эту панель.

- **Обзор:** продажи, заказы, клиенты и товары с низким остатком.
- **Товары:** добавление, редактирование, удаление, фото по ссылке, цены,
  остатки, поиск, фильтры и названия/описания на EN/RU/KK.
- **Категории:** создание, редактирование, скрытие и удаление пустых категорий.
- **Заказы:** состав, покупатель, адрес, отправка, доставка и отмена с возвратом
  остатков и обновлением статуса оплаты. Денежные возвраты здесь демонстрационные,
  как и оплата в этом учебном проекте.
- **Пользователи:** профили, блокировка, смена пароля и роли через карточку
  пользователя. Администратор может создать менеджера с рабочими правами.
- **Все разделы и настройки:** оплаты, отзывы, адреса, уведомления и права.

Покупатели не имеют доступа к панели. Доступ сотрудников проверяется по правам
Django. Товары, уже попавшие в заказы, нельзя удалить — их можно скрыть с витрины.

Запуск с существующей PostgreSQL базой на этом Mac:

```bash
cd ~/Desktop/online-shop
POSTGRES_DB=onlineshop POSTGRES_USER=postgres .venv/bin/python manage.py runserver
```

Не закрывайте Terminal, пока используете панель. Вход в неё использует отдельную
сессию администратора, поэтому после входа на витрину может потребоваться войти
ещё раз. Используйте текущий пароль администратора; пароль из демо-данных мог
быть изменён.

## REST API

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

## Demo accounts (created by seed_shop; initial password: `Shop2026!`)

| Username | Role | Where |
|---|---|---|
| aigerim, dana, timur | customer | website |
| manager | store manager | website + admin panel |
| admin | administrator | http://127.0.0.1:8000/admin |

These passwords apply to freshly seeded demo data. Existing administrators or
managers may have a different password. `create_manager` always uses the password
provided at creation; it does not use the shared demo password.

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

## Роль менеджера

Администратор назначает роль **«Менеджер магазина»** в карточке пользователя
или при его создании. Менеджер входит в ту же панель **/staff/** и получает
рабочие права на каталог, категории, заказы, отзывы и уведомления. Профили
покупателей, оплаты и адреса доступны для просмотра. Изменение ролей, паролей
пользователей и системных прав в стандартные права менеджера не входит.

В списке пользователей администратор может отфильтровать покупателей,
менеджеров и администраторов по роли. При переводе администратора в менеджеры
старые дополнительные права удаляются. Перевод в покупатели отключает доступ
к панели и удаляет группы и дополнительные права.

Создать нового менеджера локально, с вводом пароля без показа на экране:

```bash
POSTGRES_DB=onlineshop POSTGRES_USER=postgres .venv/bin/python manage.py create_manager manager --email manager@example.com
```

Команда проверяет сложность пароля и не меняет существующий аккаунт без явного
флага `--update-existing`. Для автоматизации есть `--password-stdin`: пароль
передаётся одной строкой через stdin, без записи в аргументы команды или вывод.

## Защита входа и проверка на ботов

Защита работает одновременно на витрине (`/api/auth/login/`) и в панели
сотрудников (`/admin/login/`). Оба входа используют общие счётчики в базе:

- После 3 неудачных попыток появляется одноразовый арифметический пример.
- После 5 неудачных попыток вход в этот аккаунт с этого адреса блокируется на
  300 секунд. Правильный пароль также не обходит активную блокировку.
- После 20 ошибок с одного адреса блокируются попытки по всем логинам с этого
  адреса. Заголовок `X-Forwarded-For` не позволяет сменить источник запроса.
- Перезагрузка страницы и перезапуск сервера не сбрасывают защиту. Запросы во
  время блокировки не продлевают её. После успешного входа счётчик пары
  логин/адрес сбрасывается; история ошибок с адреса сохраняется до конца окна.
- Проверка действует до 2 минут, привязана к адресу и используется один раз.
  Количество выдаваемых примеров ограничено. Скрытое поле отсекает часть
  автоматических заполнений формы.

Витрина и панель показывают оставшиеся попытки и время ожидания. Ответ API при
блокировке: HTTP 429, `code: login_locked`, `retry_after` и заголовок `Retry-After`.
Проверка запрашивается через `GET /api/auth/challenge/`, а поля `challenge_id` и
`challenge_answer` передаются вместе с логином и паролем. Настройки лимитов
находятся в `config/settings.py`. После обновления выполните `manage.py migrate`.

Арифметический пример — базовая проверка для локального учебного проекта; он не
заменяет полноценный сервис CAPTCHA. Основная защита от перебора здесь —
серверные лимиты и временная блокировка. Подход учитывает рекомендации
[OWASP по ограничению входа и CAPTCHA](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#login-throttling).
