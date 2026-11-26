"""
Performance Testing, часть 4: поведение сервера при большой нагрузке.

  * нарастающая нагрузка (10 -> 25 -> 50 -> 75 -> 100 пользователей);
  * непрерывная нагрузка несколько секунд подряд;
  * после пика сервер «приходит в себя» и снова отвечает быстро.
"""
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config, report
from .helpers import PerfTestCase, run_concurrent, summarize, timed_get

MIXED_ENDPOINTS = ["/api/categories/", config.PRODUCT_LIST_URL, "/api/products/?sort=price",
                   "/api/products/filters/", "/api/top/?kind=new", "/api/search/?q=a",
                   "/api/products/best-sellers/?limit=4"]


class LoadBehaviorTests(PerfTestCase):

    def test_ramp_up_load(self):
        """Нагрузка растёт ступенями: на каждой ступени почти все запросы успешны."""
        last_summary = None
        for users in config.RAMP_UP_USERS:
            with self.subTest(users=users):
                results, wall = run_concurrent(self.base_url, MIXED_ENDPOINTS, users)
                s = summarize(results, wall)
                last_summary = s
                report.record(f"ramp_up_{users}_users", success_rate=s["success_rate"],
                              avg_s=s["avg_s"], p95_s=s["p95_s"], total_s=wall)
                min_rate = config.SUCCESS_RATE_50 if users <= 50 else config.SUCCESS_RATE_100
                self.assertGreaterEqual(s["success_rate"], min_rate)
            time.sleep(0.5)                              # короткая пауза между ступенями
        self.assertLess(last_summary["p95_s"], config.CONCURRENT_P95_100_S)

    def test_sustained_load(self):
        """Непрерывная нагрузка LOAD_DURATION_S секунд: доля ошибок и среднее время в норме."""
        rng = random.Random(42)
        results, lock = [], threading.Lock()
        stop_at = time.perf_counter() + config.LOAD_DURATION_S

        def user():
            while time.perf_counter() < stop_at:
                with lock:
                    path = rng.choice(MIXED_ENDPOINTS)
                result = timed_get(self.base_url, path)
                with lock:
                    results.append(result)

        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=config.LOAD_WORKERS) as pool:
            for _ in range(config.LOAD_WORKERS):
                pool.submit(user)
        wall = time.perf_counter() - start

        s = summarize(results, wall)
        report.record("sustained_load", workers=config.LOAD_WORKERS, duration_s=wall,
                      requests=s["requests"], success_rate=s["success_rate"], errors_5xx=s["errors_5xx"],
                      avg_s=s["avg_s"], p95_s=s["p95_s"], req_per_s=s["req_per_s"])
        self.assertGreater(s["requests"], config.LOAD_WORKERS, "нагрузка не создалась")
        self.assertLessEqual(1 - s["success_rate"], config.LOAD_MAX_ERROR_RATE)
        self.assertLess(s["avg_s"], config.LOAD_AVG_S)

    def test_server_recovers_after_heavy_load(self):
        """После пика в 100 запросов сервер снова отвечает быстро и без ошибок."""
        run_concurrent(self.base_url, [config.PRODUCT_LIST_URL], 100)
        time.sleep(1)
        results = [self.get(config.PRODUCT_LIST_URL) for _ in range(5)]
        s = summarize(results)
        report.record("recovery_after_peak", success_rate=s["success_rate"], avg_s=s["avg_s"], max_s=s["max_s"])
        self.assertEqual(s["ok"], 5)
        self.assertLess(s["max_s"], config.RECOVERY_MAX_S)
