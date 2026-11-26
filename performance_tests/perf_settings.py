"""
Настройки Django ТОЛЬКО для автоматического тестового сервера.

Используются, когда обычный сервер (runserver) не запущен: тесты сами поднимают
временный сервер с отдельной SQLite-базой во временной папке.
Ваша основная база данных (PostgreSQL) при этом не затрагивается.
"""
import os

os.environ.setdefault("USE_SQLITE", "1")   # чтобы config.settings не требовал PostgreSQL

from config.settings import *  # noqa: E402,F401,F403

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("PERF_SQLITE_PATH", str(BASE_DIR / "performance_tests" / "reports" / "perf.sqlite3")),
        "OPTIONS": {"timeout": 30},
    }
}
DEBUG = False            # как в продакшене: без накопления SQL-запросов в памяти
ALLOWED_HOSTS = ["*"]
