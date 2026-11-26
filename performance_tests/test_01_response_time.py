"""
Performance Testing, часть 1: время ответа API.

Проверяем, что публичные эндпоинты магазина отвечают быстро:
  * каждый эндпоинт отвечает 200 и укладывается в лимит времени;
  * среднее время и p95 на серии запросов в пределах нормы;
  * ответы — корректный JSON;
  * закрытый эндпоинт (корзина) быстро отклоняет запрос без токена (401).
"""
from . import config, report
from .helpers import PerfTestCase, summarize


class ApiResponseTimeTests(PerfTestCase):

    def test_every_public_endpoint_responds_quickly(self):
        """Каждый публичный эндпоинт: статус 200 и время ответа < MAX_SINGLE_RESPONSE_S."""
        for path in config.PUBLIC_ENDPOINTS:
            with self.subTest(endpoint=path):
                result = self.get(path)
                report.record(f"response_time {path}", status=result.status,
                              time_s=result.elapsed, size_bytes=result.size)
                self.assertEqual(result.status, 200, f"{path}: ошибка {result.error}")
                self.assertLess(result.elapsed, config.MAX_SINGLE_RESPONSE_S,
                                f"{path} ответил за {result.elapsed:.3f} с")

    def test_average_response_time_over_series(self):
        """Серия из 20 запросов подряд к ключевым эндпоинтам: среднее и p95 в пределах нормы."""
        for path in ("/api/categories/", config.PRODUCT_LIST_URL, "/api/search/?q=a"):
            with self.subTest(endpoint=path):
                results = [self.get(path) for _ in range(20)]
                s = summarize(results)
                report.record(f"series_20 {path}", avg_s=s["avg_s"], p95_s=s["p95_s"], max_s=s["max_s"])
                self.assertEqual(s["ok"], 20)
                self.assertLess(s["avg_s"], config.AVG_RESPONSE_S)
                self.assertLess(s["p95_s"], config.P95_RESPONSE_S)

    def test_responses_are_valid_json(self):
        """Быстрый ответ бесполезен, если он сломан: тело каждого ответа — корректный JSON."""
        import requests
        for path in config.PUBLIC_ENDPOINTS:
            with self.subTest(endpoint=path):
                response = requests.get(self.base_url + path, timeout=config.REQUEST_TIMEOUT_S)
                self.assertEqual(response.status_code, 200)
                self.assertIn("application/json", response.headers.get("Content-Type", ""))
                response.json()          # упадёт, если JSON некорректный

    def test_protected_endpoint_rejects_fast_without_token(self):
        """Корзина без токена: быстрый отказ 401 (проверка авторизации не тормозит сервер)."""
        result = self.get(config.PROTECTED_ENDPOINT)
        report.record("unauthorized_cart_rejection", status=result.status, time_s=result.elapsed)
        self.assertEqual(result.status, 401)
        self.assertLess(result.elapsed, config.MAX_SINGLE_RESPONSE_S)
