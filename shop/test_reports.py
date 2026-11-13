"""Manager reports: sales by category, low stock, best sellers, promo usage, CSV, access."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from . import services
from .models import Address, CartItem, Category, Order, Product, PromoCode, User
from .roles import sync_role_access


class ReportTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.addr = Address.objects.create(user=self.buyer, city="Almaty", street="Abay 1")
        el = Category.objects.create(name_en="Electronics", name_ru="Электроника", name_kk="Электроника")
        bk = Category.objects.create(name_en="Books", name_ru="Книги", name_kk="Кітаптар")
        self.mouse = Product.objects.create(sku="M1", category=el, name_en="Mouse", name_ru="Мышь", name_kk="Т",
                                            price=Decimal("30"), stock_quantity=20)
        self.book = Product.objects.create(sku="B1", category=bk, name_en="Book", name_ru="Книга", name_kk="К",
                                           price=Decimal("10"), stock_quantity=4)
        PromoCode.objects.create(code="WELCOME10", discount_percent=10)
        self.order([(self.mouse, 3)], promo="WELCOME10")          # 90 - 9
        self.order([(self.book, 1)])                               # 10
        cancelled = self.order([(self.mouse, 5)])
        services.cancel_order(cancelled)                           # not counted

    def order(self, lines, promo=""):
        for p, q in lines:
            CartItem.objects.create(user=self.buyer, product=p, quantity=q)
        return services.place_order(self.buyer, self.addr, "card", promo_code=promo)

    def test_summary_ignores_cancelled_and_counts_discount(self):
        s = services.report_summary()
        self.assertEqual((s["orders"], s["cancelled"], s["units"]), (2, 1, 4))
        self.assertEqual(s["revenue"], Decimal("91.00"))
        self.assertEqual(s["discounts"], Decimal("9.00"))
        self.assertEqual(s["avg_order"], Decimal("45.50"))

    def test_sales_by_category(self):
        rows = services.report_sales_by_category()
        self.assertEqual([(r["name"], r["units"], r["revenue"]) for r in rows],
                         [("Электроника", 3, Decimal("90.00")), ("Книги", 1, Decimal("10.00"))])
        self.assertEqual(rows[0]["share"], 90.0)

    def test_period_filter(self):
        Order.objects.update(created_at=timezone.now() - timedelta(days=40))
        self.assertEqual(services.report_summary(timezone.now() - timedelta(days=30))["orders"], 0)
        self.assertEqual(services.report_sales_by_category(timezone.now() - timedelta(days=30)), [])

    def test_low_stock_and_promo_usage(self):
        self.assertEqual([p.sku for p in services.report_low_stock(5)], ["B1"])   # 4 left
        self.assertEqual(services.report_promo_usage()[0]["orders"], 1)

    def test_page_and_csv_for_manager_only(self):
        self.assertEqual(self.client.get("/staff/reports/").status_code, 302)    # not logged in -> login
        manager = User.objects.create_user("manager", "m@ex.com", "Shop2026!", role="manager")
        sync_role_access(manager)
        self.client.force_login(manager)
        page = self.client.get("/staff/reports/?period=all")
        self.assertContains(page, "Продажи по категориям")
        self.assertContains(page, "Электроника")
        csv = self.client.get("/staff/reports/categories.csv?period=all")
        self.assertEqual(csv["Content-Type"], "text/csv; charset=utf-8")
        self.assertIn("Электроника,3,90.00,90.0", csv.content.decode("utf-8-sig"))
        self.client.force_login(self.buyer)
        self.assertNotEqual(self.client.get("/staff/reports/").status_code, 200)
