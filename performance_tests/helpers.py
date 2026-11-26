"""Общие инструменты: замер времени запроса, пачка одновременных запросов, статистика."""
import math
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Optional

import requests

from . import config
from .server import get_base_url


@dataclass
class Result:
    path: str
    status: int                  # HTTP-статус, 0 = запрос вообще не получил ответа
    elapsed: float               # секунды (вместе с загрузкой тела ответа и повторными попытками)
    size: int = 0                # размер ответа в байтах
    error: Optional[str] = None
    retries: int = 0

    @property
    def ok(self):
        return self.status == 200


def timed_get(base_url, path, timeout=None, retries=2):
    """GET-запрос с замером времени. Сбой соединения повторяется (при 100 одновременных
    подключениях ОС иногда отбрасывает часть из них — реальный браузер тоже повторил бы)."""
    timeout = timeout or config.REQUEST_TIMEOUT_S
    start = time.perf_counter()
    error = None
    for attempt in range(retries + 1):
        try:
            response = requests.get(base_url + path, timeout=timeout)
            return Result(path, response.status_code, time.perf_counter() - start,
                          len(response.content), None, attempt)
        except requests.exceptions.ConnectionError as exc:
            error = f"{type(exc).__name__}: {exc}"
            time.sleep(0.2)
        except requests.RequestException as exc:
            error = f"{type(exc).__name__}: {exc}"
            break
    return Result(path, 0, time.perf_counter() - start, 0, error, retries)


def run_concurrent(base_url, paths, users):
    """Отправляет `users` запросов ОДНОВРЕМЕННО (все потоки стартуют по сигналу барьера).
    Возвращает (список Result, общее время пачки)."""
    barrier = threading.Barrier(users, timeout=60)

    def worker(i):
        barrier.wait()
        return timed_get(base_url, paths[i % len(paths)])

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=users) as pool:
        results = list(pool.map(worker, range(users)))
    return results, time.perf_counter() - start


def percentile(values, pct):
    if not values:
        return 0.0
    ordered = sorted(values)
    index = max(0, min(len(ordered) - 1, math.ceil(pct / 100 * len(ordered)) - 1))
    return ordered[index]


def summarize(results, wall=None):
    times = [r.elapsed for r in results]
    ok = sum(1 for r in results if r.ok)
    total = len(results)
    summary = {
        "requests": total,
        "ok": ok,
        "success_rate": ok / total if total else 0.0,
        "errors_5xx": sum(1 for r in results if r.status >= 500),
        "min_s": min(times) if times else 0.0,
        "avg_s": sum(times) / total if total else 0.0,
        "p95_s": percentile(times, 95),
        "max_s": max(times) if times else 0.0,
    }
    if wall:
        summary["total_s"] = wall
        summary["req_per_s"] = total / wall
    return summary


class PerfTestCase(unittest.TestCase):
    """Базовый класс: находит/запускает сервер и «прогревает» его (первый запрос всегда медленнее)."""

    base_url = None

    @classmethod
    def setUpClass(cls):
        cls.base_url = get_base_url()
        for _ in range(3):
            timed_get(cls.base_url, config.PRODUCT_LIST_URL)
            timed_get(cls.base_url, "/api/categories/")

    def get(self, path):
        return timed_get(self.base_url, path)
