"""
Настройки тестов производительности (Performance Testing) для SaudaGo Online Shop.

Все пороги можно менять здесь или через переменные окружения, например:
    PERF_MAX_SINGLE_RESPONSE_S=1.0 pytest performance_tests
Пороги специально сделаны с запасом (локальный сервер разработки, не production),
чтобы тесты были стабильными на любом ноутбуке команды.
"""
import os


def _float(name, default):
    return float(os.environ.get(name, default))


def _int(name, default):
    return int(os.environ.get(name, default))


# ---------------------------------------------------------------- адрес сервера
# Если PERF_BASE_URL не задан, тесты ищут сервер на DEFAULT_URL.
# Если там никого нет, тесты сами запускают временный сервер (SQLite + демо-данные).
DEFAULT_URL = "http://127.0.0.1:8000"
EXPLICIT_BASE_URL = os.environ.get("PERF_BASE_URL")          # например http://127.0.0.1:8000
SERVER_START_TIMEOUT_S = _int("PERF_SERVER_START_TIMEOUT_S", 180)

# ---------------------------------------------------------------- публичные эндпоинты (GET, без токена)
PUBLIC_ENDPOINTS = [
    "/api/categories/",
    "/api/products/",
    "/api/products/?sort=price",
    "/api/products/?category=1",
    "/api/products/?q=a",
    "/api/products/filters/",
    "/api/products/best-sellers/?limit=4",
    "/api/top/?kind=hits",
    "/api/top/?kind=new",
    "/api/search/?q=a",
]
PRODUCT_LIST_URL = "/api/products/"
PROTECTED_ENDPOINT = "/api/cart/"                             # без токена должен вернуть 401

# ---------------------------------------------------------------- пороги: время ответа (секунды)
REQUEST_TIMEOUT_S = _float("PERF_REQUEST_TIMEOUT_S", 60)       # таймаут одного HTTP-запроса
MAX_SINGLE_RESPONSE_S = _float("PERF_MAX_SINGLE_RESPONSE_S", 2.0)    # один запрос к любому API
AVG_RESPONSE_S = _float("PERF_AVG_RESPONSE_S", 1.0)                  # среднее по серии запросов
P95_RESPONSE_S = _float("PERF_P95_RESPONSE_S", 2.0)                  # 95-й перцентиль серии

# ---------------------------------------------------------------- пороги: список товаров
MAX_PRODUCT_LIST_S = _float("PERF_MAX_PRODUCT_LIST_S", 3.0)          # один запрос списка товаров
CATALOG_PAGE_TOTAL_S = _float("PERF_CATALOG_PAGE_TOTAL_S", 5.0)      # все запросы главной страницы подряд
SERIES_REQUESTS = _int("PERF_SERIES_REQUESTS", 30)                   # длина серии последовательных запросов

# ---------------------------------------------------------------- пороги: одновременные запросы
SUCCESS_RATE_50 = _float("PERF_SUCCESS_RATE_50", 0.95)               # доля успешных ответов при 50 пользователях
SUCCESS_RATE_100 = _float("PERF_SUCCESS_RATE_100", 0.90)             # доля успешных ответов при 100 пользователях
CONCURRENT_P95_50_S = _float("PERF_CONCURRENT_P95_50_S", 10.0)
CONCURRENT_P95_100_S = _float("PERF_CONCURRENT_P95_100_S", 15.0)
CONCURRENT_TOTAL_S = _float("PERF_CONCURRENT_TOTAL_S", 60.0)         # вся пачка запросов должна завершиться за это время

# ---------------------------------------------------------------- пороги: нагрузка
RAMP_UP_USERS = [10, 25, 50, 75, 100]                                # ступени нарастающей нагрузки
LOAD_DURATION_S = _int("PERF_LOAD_DURATION_S", 10)                   # длительность непрерывной нагрузки
LOAD_WORKERS = _int("PERF_LOAD_WORKERS", 20)                         # параллельных «пользователей» при непрерывной нагрузке
LOAD_MAX_ERROR_RATE = _float("PERF_LOAD_MAX_ERROR_RATE", 0.05)       # допустимая доля ошибок
LOAD_AVG_S = _float("PERF_LOAD_AVG_S", 3.0)                          # среднее время ответа при непрерывной нагрузке
RECOVERY_MAX_S = _float("PERF_RECOVERY_MAX_S", 4.0)                  # время ответа после нагрузки (сервер «пришёл в себя»)
