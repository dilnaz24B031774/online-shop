"""
Performance Testing, часть 2: скорость загрузки списка товаров.

Список товаров (/api/products/) — самый «тяжёлый» публичный запрос: он отдаёт весь каталог.
Проверяем скорость списка, фильтров и сортировки, сценарий главной страницы и карточки товара.
"""
from . import config, report
from .helpers import PerfTestCase, summarize

FILTERED_LISTS = [
    "/api/products/?sort=price",
    "/api/products/?sort=-price",
    "/api/products/?sort=name",
    "/api/products/?sort=rating",
    "/api/products/?sort=popular",
    "/api/products/?category=1",
    "/api/products/?in_stock=1",
    "/api/products/?min_price=5&max_price=100",
    "/api/products/?q=a",
]


class ProductListSpeedTests(PerfTestCase):

    def test_product_list_loads_fast(self):
        """Один запрос списка товаров: 200, непустой список, время < MAX_PRODUCT_LIST_S."""
        result = self.get(config.PRODUCT_LIST_URL)
        report.record("product_list_single", time_s=result.elapsed, size_kb=result.size / 1024)
        self.assertEqual(result.status, 200)
        self.assertGreater(result.size, 2, "список товаров пустой")
        self.assertLess(result.elapsed, config.MAX_PRODUCT_LIST_S)

    def test_product_list_average_speed(self):
        """Серия запросов списка товаров: среднее и p95 в пределах нормы."""
        results = [self.get(config.PRODUCT_LIST_URL) for _ in range(config.SERIES_REQUESTS)]
        s = summarize(results)
        report.record(f"product_list_series_{config.SERIES_REQUESTS}", avg_s=s["avg_s"],
                      p95_s=s["p95_s"], max_s=s["max_s"])
        self.assertEqual(s["ok"], config.SERIES_REQUESTS)
        self.assertLess(s["avg_s"], config.AVG_RESPONSE_S)
        self.assertLess(s["p95_s"], config.P95_RESPONSE_S)

    def test_filtered_and_sorted_lists_are_fast(self):
        """Фильтры и сортировки каталога не замедляют загрузку сверх лимита."""
        for path in FILTERED_LISTS:
            with self.subTest(endpoint=path):
                result = self.get(path)
                report.record(f"product_list_filter {path}", time_s=result.elapsed)
                self.assertEqual(result.status, 200, result.error)
                self.assertLess(result.elapsed, config.MAX_PRODUCT_LIST_S)

    def test_home_page_scenario_total_time(self):
        """Сценарий открытия каталога: категории + фильтры + список + хиты — суммарно быстро."""
        steps = ["/api/categories/", "/api/products/filters/", config.PRODUCT_LIST_URL,
                 "/api/products/best-sellers/?limit=4", "/api/top/?kind=new"]
        results = [self.get(p) for p in steps]
        total = sum(r.elapsed for r in results)
        report.record("catalog_page_scenario", steps=len(steps), total_s=total)
        self.assertTrue(all(r.ok for r in results))
        self.assertLess(total, config.CATALOG_PAGE_TOTAL_S)

    def test_product_detail_pages_are_fast(self):
        """Карточки первых 5 товаров открываются быстро."""
        import requests
        products = requests.get(self.base_url + config.PRODUCT_LIST_URL,
                                timeout=config.REQUEST_TIMEOUT_S).json()
        self.assertTrue(products, "в каталоге нет товаров")
        for product in products[:5]:
            with self.subTest(product_id=product["id"]):
                result = self.get(f"/api/products/{product['id']}/")
                report.record(f"product_detail id={product['id']}", time_s=result.elapsed)
                self.assertEqual(result.status, 200)
                self.assertLess(result.elapsed, config.MAX_SINGLE_RESPONSE_S)

    def test_repeated_requests_do_not_slow_down(self):
        """Стабильность: последние 10 запросов из 40 не намного медленнее первых 10."""
        times = [self.get(config.PRODUCT_LIST_URL).elapsed for _ in range(40)]
        first, last = sum(times[:10]) / 10, sum(times[-10:]) / 10
        report.record("product_list_stability", first10_avg_s=first, last10_avg_s=last)
        self.assertLessEqual(last, first * 3 + 0.5)
