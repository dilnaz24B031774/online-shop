"""
Нагрузочный тест Locust для SaudaGo Online Shop (необязательная часть, дополняет pytest-тесты).

Запуск без браузера (рекомендуется для отчёта), 50 пользователей, 30 секунд:
    locust -f performance_tests/locustfile.py --headless -u 50 -r 10 -t 30s \
           --host http://127.0.0.1:8000 --html performance_tests/reports/locust_report.html

Запуск с веб-интерфейсом: locust -f performance_tests/locustfile.py --host http://127.0.0.1:8000
и откройте http://localhost:8089

  -u  сколько одновременных пользователей
  -r  сколько новых пользователей запускать в секунду
  -t  сколько времени идёт тест
"""
import random

from locust import HttpUser, between, task


class ShopVisitor(HttpUser):
    """Обычный покупатель без входа в аккаунт: смотрит каталог, ищет, открывает карточки."""

    wait_time = between(0.5, 2)          # пауза между действиями, как у живого человека
    product_ids = [1]

    def on_start(self):
        with self.client.get("/api/products/", name="/api/products/ (start)", catch_response=True) as r:
            if r.status_code == 200 and r.json():
                self.product_ids = [p["id"] for p in r.json()[:20]]
                r.success()
            else:
                r.failure(f"status {r.status_code}")

    @task(5)
    def product_list(self):
        self.client.get("/api/products/", name="/api/products/")

    @task(3)
    def categories(self):
        self.client.get("/api/categories/", name="/api/categories/")

    @task(3)
    def sorted_list(self):
        sort = random.choice(["price", "-price", "name", "rating", "popular"])
        self.client.get(f"/api/products/?sort={sort}", name="/api/products/?sort=[x]")

    @task(2)
    def filters(self):
        self.client.get("/api/products/filters/", name="/api/products/filters/")

    @task(2)
    def search(self):
        self.client.get("/api/search/?q=a", name="/api/search/?q=[x]")

    @task(2)
    def top_products(self):
        self.client.get("/api/top/?kind=new", name="/api/top/?kind=[x]")

    @task(4)
    def product_detail(self):
        self.client.get(f"/api/products/{random.choice(self.product_ids)}/", name="/api/products/[id]/")
