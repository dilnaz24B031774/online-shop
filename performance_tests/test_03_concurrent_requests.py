"""
Performance Testing, часть 3: одновременные запросы (50 и 100 пользователей).

Все потоки стартуют одновременно (барьер), как будто 50/100 человек одновременно открыли магазин.
Проверяем долю успешных ответов, время ответа (p95) и общее время пачки.
"""
from . import config, report
from .helpers import PerfTestCase, run_concurrent, summarize

MIXED_ENDPOINTS = ["/api/categories/", config.PRODUCT_LIST_URL, "/api/products/?sort=price",
                   "/api/products/filters/", "/api/top/?kind=new", "/api/search/?q=a"]


class ConcurrentRequestsTests(PerfTestCase):

    def _check(self, name, users, paths, min_success, max_p95):
        results, wall = run_concurrent(self.base_url, paths, users)
        s = summarize(results, wall)
        report.record(name, users=users, success_rate=s["success_rate"], errors_5xx=s["errors_5xx"],
                      avg_s=s["avg_s"], p95_s=s["p95_s"], max_s=s["max_s"],
                      total_s=wall, req_per_s=s["req_per_s"])
        self.assertEqual(s["requests"], users)
        self.assertGreaterEqual(s["success_rate"], min_success,
                                f"успешных {s['ok']} из {users}; ошибки: "
                                f"{sorted({r.error or r.status for r in results if not r.ok})[:3]}")
        self.assertLess(s["p95_s"], max_p95)
        self.assertLess(wall, config.CONCURRENT_TOTAL_S)
        self.assertTrue(all(r.size > 0 for r in results if r.ok), "получен пустой ответ")

    def test_50_simultaneous_requests_to_product_list(self):
        """50 одновременных запросов списка товаров."""
        self._check("concurrent_50_product_list", 50, [config.PRODUCT_LIST_URL],
                    config.SUCCESS_RATE_50, config.CONCURRENT_P95_50_S)

    def test_100_simultaneous_requests_to_product_list(self):
        """100 одновременных запросов списка товаров."""
        self._check("concurrent_100_product_list", 100, [config.PRODUCT_LIST_URL],
                    config.SUCCESS_RATE_100, config.CONCURRENT_P95_100_S)

    def test_100_simultaneous_requests_to_mixed_endpoints(self):
        """100 одновременных запросов к разным страницам (категории, каталог, поиск, фильтры...)."""
        self._check("concurrent_100_mixed", 100, MIXED_ENDPOINTS,
                    config.SUCCESS_RATE_100, config.CONCURRENT_P95_100_S)
