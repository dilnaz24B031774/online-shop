# Performance Testing — SaudaGo Online Shop

Тесты производительности на Python (`pytest` + `requests`, плюс необязательный `Locust`).
Проверяют: время ответа API, скорость списка товаров, 50–100 одновременных запросов, поведение сервера под нагрузкой.

## Структура (папка кладётся в корень проекта, рядом с `manage.py`)

```
onlineshop/
├── manage.py
├── config/ shop/ frontend/ ...
└── performance_tests/
    ├── README.md                      эта инструкция
    ├── requirements-perf.txt          pytest, requests, locust
    ├── pytest.ini                     настройки pytest
    ├── conftest.py                    печатает таблицу метрик в конце запуска
    ├── config.py                      ВСЕ пороги и адреса (менять здесь)
    ├── helpers.py                     замер времени запроса, пачка одновременных запросов, статистика
    ├── server.py                      находит сервер или запускает временный
    ├── run_test_server.py             временный сервер (SQLite + демо-данные)
    ├── perf_settings.py               настройки Django для временного сервера
    ├── report.py                      запись отчёта в reports/
    ├── test_01_response_time.py       1. время ответа API
    ├── test_02_product_list_speed.py  2. скорость загрузки списка товаров
    ├── test_03_concurrent_requests.py 3. 50 и 100 одновременных запросов
    ├── test_04_load_behavior.py       4. поведение при нагрузке (ступени, непрерывная нагрузка, восстановление)
    ├── locustfile.py                  (необязательно) нагрузка через Locust
    └── reports/                       сюда пишутся отчёты (в git не попадают)
```

## Установка (один раз)

Из корня проекта (там, где `manage.py`):

```bash
# Mac / Linux
source venv/bin/activate
# Windows
venv\Scripts\activate

pip install -r requirements.txt
pip install -r performance_tests/requirements-perf.txt
```

## Запуск тестов

Из корня проекта, с включённым venv.

**Вариант A — ничего не запускать заранее (самый простой).**
Если сервер не запущен, тесты сами поднимут временный сервер на SQLite с демо-данными
(`seed_shop`, ~120 товаров) и выключат его после тестов. Ваша PostgreSQL-база не затрагивается.

```bash
python -m pytest performance_tests
```

Первый запуск может занять до минуты (создание временной базы), сами тесты идут ~30 секунд.

**Вариант B — на вашем настоящем сервере.**
Если в другом терминале уже работает `python manage.py runserver` (порт 8000), тесты найдут его сами.
Другой адрес: `PERF_BASE_URL=http://127.0.0.1:9000 python -m pytest performance_tests`
(Windows PowerShell: `$env:PERF_BASE_URL="http://127.0.0.1:9000"; python -m pytest performance_tests`).

Тесты только **читают** данные (GET), ничего не создают и не удаляют в базе.

**Запуск отдельных частей:**

```bash
python -m pytest performance_tests/test_01_response_time.py
python -m pytest performance_tests/test_02_product_list_speed.py
python -m pytest performance_tests/test_03_concurrent_requests.py
python -m pytest performance_tests/test_04_load_behavior.py
```

Без pytest тоже работает: `python -m unittest discover -s performance_tests -t . -v`

## Результат

* В консоли: список тестов `PASSED` и таблица метрик (среднее, p95, максимум, запросов в секунду).
* Файлы для отчёта по проекту: `performance_tests/reports/performance_report.md` и `.json`.

Ожидаемый итог: `16 passed`.

## Необязательно: Locust

```bash
locust -f performance_tests/locustfile.py --headless -u 50 -r 10 -t 30s \
       --host http://127.0.0.1:8000 --html performance_tests/reports/locust_report.html
```

Нужен запущенный `runserver`. HTML-отчёт Locust с графиками появится в `reports/locust_report.html`.
Без `--headless` откроется веб-интерфейс на http://localhost:8089.

## Что именно проверяют тесты

| Файл | Что проверяет | Пороги (в `config.py`) |
|---|---|---|
| test_01 | каждый публичный эндпоинт отвечает 200 быстро; среднее/p95 на серии из 20 запросов; ответ — валидный JSON; корзина без токена даёт быстрый 401 | один запрос < 2 с, среднее < 1 с, p95 < 2 с |
| test_02 | список товаров, 9 вариантов фильтров/сортировок, сценарий открытия каталога, 5 карточек товаров, стабильность на 40 запросах подряд | список < 3 с, сценарий < 5 с |
| test_03 | 50 и 100 одновременных запросов (все стартуют разом): список товаров и смесь разных страниц | успех ≥ 95% (50) / ≥ 90% (100), p95 < 10 / 15 с |
| test_04 | нагрузка растёт 10→25→50→75→100; 10 секунд непрерывной нагрузки (20 пользователей); восстановление после пика | ошибок ≤ 5%, среднее < 3 с, после пика < 4 с |

Пороги намеренно мягкие (учтён сервер разработки `runserver` на обычном ноутбуке).
Чтобы ужесточить, измените значения в `config.py` или задайте переменной окружения,
например `PERF_MAX_SINGLE_RESPONSE_S=0.5`.

## Если что-то не работает

| Проблема | Решение |
|---|---|
| `Временный сервер не запустился` | активируйте venv и выполните `pip install -r requirements.txt` |
| `PERF_BASE_URL=... не отвечает` | запустите `python manage.py runserver` или уберите переменную |
| `ModuleNotFoundError: pytest` | `pip install -r performance_tests/requirements-perf.txt` |
| На Windows тест на 100 пользователей иногда ниже порога | запустите ещё раз или снизьте `PERF_SUCCESS_RATE_100` (сервер разработки на Windows хуже держит пачки подключений) |
