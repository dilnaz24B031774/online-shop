"""
Запуск временного сервера для тестов производительности.

Запускается автоматически из performance_tests/server.py, вручную не нужен.
Что делает: создаёт временную SQLite-базу -> migrate -> seed_shop -> runserver.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ["DJANGO_SETTINGS_MODULE"] = "performance_tests.perf_settings"

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402
from django.core.servers import basehttp  # noqa: E402

# Большая очередь подключений, чтобы 100 одновременных запросов не отбрасывались ОС.
basehttp.WSGIServer.request_queue_size = 256

port = sys.argv[1] if len(sys.argv) > 1 else "8765"

call_command("migrate", interactive=False, verbosity=0)

from shop.models import Product  # noqa: E402

if not Product.objects.exists():
    call_command("seed_shop")

call_command("runserver", f"127.0.0.1:{port}", use_reloader=False, verbosity=0)
