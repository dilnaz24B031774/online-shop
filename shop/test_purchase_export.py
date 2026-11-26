"""Admin purchase export: /staff/reports/purchases.csv and .pdf."""
import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from . import services
from .models import Address, CartItem, Category, Order, Product, PromoCode, User
from .roles import sync_role_access


class PurchaseExportTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!", first_name="=HYPERLINK(\"x\")",
                                              phone="+77001234567")
        self.addr = Address.objects.create(user=self.buyer, city="Almaty", street="Abay 1")
        cat = Category.objects.create(name_en="Electronics", name_ru="Электроника", name_kk="Электроника")
        self.mouse = Product.objects.create(sku="M1", category=cat, name_en="Mouse", name_ru="Мышь", name_kk="Т",
                                            price=Decimal("30"), stock_quantity=20)
        self.book = Product.objects.create(sku="B1", category=cat, name_en="Book", name_ru="Книга", name_kk="К",
                                           price=Decimal("10"), stock_quantity=20)
        PromoCode.objects.create(code="WELCOME10", discount_percent=10)
        self.paid = self.order([(self.mouse, 2), (self.book, 1)], promo="WELCOME10")
        self.cancelled = self.order([(self.book, 3)])
        services.cancel_order(self.cancelled)
        self.admin = User.objects.create_superuser("boss", "boss@ex.com", "Shop2026!")

    def order(self, lines, promo=""):
        for product, quantity in lines:
            CartItem.objects.create(user=self.buyer, product=product, quantity=quantity)
        return services.place_order(self.buyer, self.addr, "card", promo_code=promo)

    def csv_rows(self, query=""):
        response = self.client.get("/staff/reports/purchases.csv" + query)
        self.assertEqual(response.status_code, 200)
        text = response.content.decode("utf-8-sig")
        return list(csv.reader(io.StringIO(text), delimiter=";"))

    def test_csv_has_one_row_per_item_with_customer_and_payment(self):
        self.client.force_login(self.admin)
        rows = self.csv_rows()
        header, body = rows[0], rows[1:]
        self.assertIn("Покупатель", header)
        self.assertEqual(len(body), 3)                       # 2 items + 1 item in the cancelled order
        paid_rows = [r for r in body if r[0] == str(self.paid.pk)]
        self.assertEqual({r[header.index("SKU")] for r in paid_rows}, {"M1", "B1"})
        row = paid_rows[0]
        self.assertEqual(row[header.index("Email")], "a@ex.com")
        self.assertEqual(row[header.index("Способ оплаты")], "Карта")
        self.assertEqual(row[header.index("Промокод")], "WELCOME10")
        self.assertEqual(row[header.index("Итого заказа, $")], str(self.paid.total_amount))

    def test_csv_neutralises_spreadsheet_formulas(self):
        self.client.force_login(self.admin)
        rows = self.csv_rows()
        name = rows[1][rows[0].index("Покупатель")]
        self.assertEqual(name, "'=HYPERLINK(\"x\")")

    def test_filters_by_status_date_and_demo(self):
        self.client.force_login(self.admin)
        self.assertEqual({r[0] for r in self.csv_rows("?status=cancelled")[1:]}, {str(self.cancelled.pk)})
        Order.objects.filter(pk=self.paid.pk).update(created_at=timezone.now() - timedelta(days=60))
        self.assertEqual({r[0] for r in self.csv_rows()[1:]}, {str(self.cancelled.pk)})   # last 30 days by default
        old = (timezone.localdate() - timedelta(days=61)).isoformat()
        self.assertEqual(len(self.csv_rows(f"?date_from={old}")) - 1, 3)
        Order.objects.update(is_demo=True)
        self.assertEqual(len(self.csv_rows(f"?date_from={old}")), 1)                       # demo hidden
        self.assertEqual(len(self.csv_rows(f"?date_from={old}&demo=1")), 4)

    def test_bad_filters_fall_back_to_defaults(self):
        self.client.force_login(self.admin)
        self.assertEqual(len(self.csv_rows("?date_from=nope&status=evil")), 4)

    def test_pdf_is_a_real_pdf(self):
        self.client.force_login(self.admin)
        response = self.client.get("/staff/reports/purchases.pdf")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("attachment", response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 1500)

    def test_pdf_with_no_orders(self):
        self.client.force_login(self.admin)
        Order.objects.update(created_at=timezone.now() - timedelta(days=400))
        response = self.client.get("/staff/reports/purchases.pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_access(self):
        for url in ("/staff/reports/purchases.csv", "/staff/reports/purchases.pdf"):
            self.client.logout()
            self.assertEqual(self.client.get(url).status_code, 302)          # login page
            self.client.force_login(self.buyer)
            self.assertNotEqual(self.client.get(url).status_code, 200)       # customers never
        manager = User.objects.create_user("manager", "m@ex.com", "Shop2026!", role="manager")
        sync_role_access(manager)
        self.client.force_login(manager)
        allowed = manager.has_perm("shop.view_order") and manager.has_perm("shop.view_user")
        self.assertEqual(self.client.get("/staff/reports/purchases.csv").status_code, 200 if allowed else 403)

    def test_reports_page_shows_export_form_to_admin(self):
        self.client.force_login(self.admin)
        page = self.client.get("/staff/reports/").content.decode()
        self.assertIn("Выгрузка всех покупок", page)
        self.assertIn("/staff/reports/purchases.pdf", page)
