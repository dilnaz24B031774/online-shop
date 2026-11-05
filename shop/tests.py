"""
Database tests:   python manage.py test shop
Each test proves that one rule protects the data.
"""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Address, CartItem, Category, Order, OrderItem, Payment, Product, Review, User
from .services import OutOfStockError, best_sellers, place_order, search


class ShopDatabaseTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("aigerim", "aigerim@example.com", "Shop2026!")
        cls.address = Address.objects.create(user=cls.user, city="Almaty", street="Abay Ave 10",
                                             is_default=True)
        cls.cat = Category.objects.create(name_en="Electronics", name_ru="Электроника",
                                          name_kk="Электроника")
        cls.mouse = Product.objects.create(category=cls.cat, sku="EL-MOUSE-01",
                                           name_en="Wireless Mouse", name_ru="Беспроводная мышь",
                                           name_kk="Сымсыз тінтуір",
                                           price=Decimal("25.00"), stock_quantity=6)

    def assertRuleBlocks(self, func):
        """The database must reject the row (IntegrityError)."""
        with self.assertRaises(IntegrityError), transaction.atomic():
            func()

    # ---------- primary keys and UNIQUE ----------
    def test_password_is_stored_as_hash(self):
        self.assertNotIn("Shop2026!", self.user.password)
        self.assertTrue(self.user.password.startswith("pbkdf2_sha256$"))

    def test_same_email_rejected(self):
        self.assertRuleBlocks(lambda: User.objects.create_user("aigerim2", "aigerim@example.com", "x"))

    def test_same_primary_key_rejected(self):
        self.assertRuleBlocks(lambda: Category.objects.create(id=self.cat.id, name_en="Other"))

    def test_same_sku_rejected(self):
        self.assertRuleBlocks(lambda: Product.objects.create(
            category=self.cat, sku="EL-MOUSE-01", name_en="Copy", price=1, stock_quantity=1))

    # ---------- CHECK rules ----------
    def test_negative_price_rejected(self):
        self.assertRuleBlocks(lambda: Product.objects.create(
            category=self.cat, sku="BAD-1", name_en="Bad", price=Decimal("-5"), stock_quantity=1))

    def test_negative_stock_rejected(self):
        self.assertRuleBlocks(lambda: Product.objects.filter(pk=self.mouse.pk)
                              .update(stock_quantity=-1))

    def test_rating_must_be_1_to_5(self):
        self.assertRuleBlocks(lambda: Review.objects.create(user=self.user, product=self.mouse, rating=6))

    def test_invalid_order_status_rejected(self):
        self.assertRuleBlocks(lambda: Order.objects.create(
            user=self.user, shipping_address="Almaty", status="lost"))

    def test_only_one_default_address(self):
        self.assertRuleBlocks(lambda: Address.objects.create(
            user=self.user, city="Almaty", street="Tole Bi 59", is_default=True))

    # ---------- foreign keys ----------
    def test_order_needs_existing_user(self):
        # Django creates foreign keys as "checked at COMMIT" in PostgreSQL,
        # so here we ask the database to check them immediately.
        from django.db import connection

        def create_orphan():
            Order.objects.create(user_id=999999, shipping_address="Almaty")
            connection.check_constraints()
        self.assertRuleBlocks(create_orphan)

    def test_cannot_delete_product_that_was_sold(self):
        order = Order.objects.create(user=self.user, shipping_address="Almaty")
        OrderItem.objects.create(order=order, product=self.mouse, quantity=1, unit_price=25)
        from django.db.models import ProtectedError
        with self.assertRaises(ProtectedError):
            self.mouse.delete()

    # ---------- transaction ----------
    def test_checkout_creates_order_and_reduces_stock(self):
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=2)
        order = place_order(self.user, self.address, "card")
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock_quantity, 4)
        self.assertEqual(order.total_amount, Decimal("50.00"))
        self.assertEqual(order.payment.status, Payment.Status.PAID)
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_checkout_rolls_back_when_not_enough_stock(self):
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=10)
        with self.assertRaises(OutOfStockError):
            place_order(self.user, self.address, "card")
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock_quantity, 6)        # stock unchanged
        self.assertEqual(Order.objects.count(), 0)           # no half-finished order
        self.assertTrue(CartItem.objects.filter(user=self.user).exists())  # cart kept

    # ---------- search and reports ----------
    def test_search_works_in_russian_and_kazakh(self):
        self.assertIn(self.mouse, search("мышь")["products"])
        self.assertIn(self.mouse, search("тінтуір")["products"])
        self.assertIn(self.cat, search("electro")["categories"])

    def test_best_sellers_ignore_cancelled_orders(self):
        paid = Order.objects.create(user=self.user, shipping_address="A", status="paid")
        OrderItem.objects.create(order=paid, product=self.mouse, quantity=3, unit_price=25)
        cancelled = Order.objects.create(user=self.user, shipping_address="A", status="cancelled")
        OrderItem.objects.create(order=cancelled, product=self.mouse, quantity=50, unit_price=25)
        top = best_sellers()[0]
        self.assertEqual(top.units_sold, 3)
        self.assertEqual(top.revenue, Decimal("75.00"))


class PasswordStrengthTests(TestCase):
    """Task: password strength. 6 cases: 5 weak passwords + 1 strong."""

    def try_register(self, password):
        from .services import register_customer
        return register_customer("dilnaz", "dilnaz@example.com", password)

    def assertWeak(self, password):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            self.try_register(password)
        self.assertFalse(User.objects.filter(username="dilnaz").exists())  # nothing saved

    def test_too_short(self):
        self.assertWeak("Ab1")

    def test_no_capital_letter(self):
        self.assertWeak("shop20266")

    def test_no_number(self):
        self.assertWeak("ShopShopShop")

    def test_only_numbers_and_common(self):
        self.assertWeak("12345678")

    def test_similar_to_username(self):
        self.assertWeak("Dilnaz2026")

    def test_strong_password_saved_as_hash(self):
        user = self.try_register("Shop2026!")
        self.assertTrue(User.objects.filter(username="dilnaz").exists())
        self.assertNotIn("Shop2026!", user.password)
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
        self.assertTrue(user.check_password("Shop2026!"))


class ApiFlowTests(TestCase):
    """The full customer flow through the REST API (what Angular does)."""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name_en="Electronics", name_ru="Электроника")
        cls.mouse = Product.objects.create(category=cat, sku="EL-MOUSE-01", name_en="Wireless Mouse",
                                           name_ru="Беспроводная мышь", price=Decimal("25.00"),
                                           stock_quantity=6)

    def test_register_login_cart_checkout(self):
        from rest_framework.test import APIClient
        c = APIClient()
        # weak password is refused
        r = c.post("/api/auth/register/", {"username": "dilnaz", "email": "d@ex.com",
                                           "password": "12345"}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("password", r.json())
        # strong password -> account + tokens
        r = c.post("/api/auth/register/", {"username": "dilnaz", "email": "d@ex.com",
                                           "password": "Shop2026!"}, format="json")
        self.assertEqual(r.status_code, 201)
        # login returns a JWT token
        r = c.post("/api/auth/login/", {"username": "dilnaz", "password": "Shop2026!"}, format="json")
        self.assertEqual(r.status_code, 200)
        c.credentials(HTTP_AUTHORIZATION="Bearer " + r.json()["access"])
        # cart without token is refused
        self.assertEqual(APIClient().get("/api/cart/").status_code, 401)
        # add address and product, then checkout
        addr = c.post("/api/addresses/", {"city": "Almaty", "street": "Abay 10"}, format="json").json()
        self.assertEqual(c.post("/api/cart/", {"product_id": self.mouse.id, "quantity": 7},
                                format="json").status_code, 400)          # more than stock
        c.post("/api/cart/", {"product_id": self.mouse.id, "quantity": 2}, format="json")
        r = c.post("/api/checkout/", {"address_id": addr["id"], "method": "card"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["total_amount"], "50.00")
        self.assertEqual(len(c.get("/api/orders/").json()), 1)
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock_quantity, 4)

    def test_catalogue_and_search_are_public(self):
        from rest_framework.test import APIClient
        c = APIClient()
        self.assertEqual(len(c.get("/api/products/").json()), 1)
        self.assertEqual(c.get("/api/search/?q=мышь").json()["products"][0]["sku"], "EL-MOUSE-01")



class CancelOrderTests(TestCase):
    """Cancel + refund: stock comes back, payment is refunded, rules are respected."""

    def setUp(self):
        from .services import place_order
        self.user = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.address = Address.objects.create(user=self.user, city="Almaty", street="Abay 10", is_default=True)
        cat = Category.objects.create(name_en="Electronics")
        self.mouse = Product.objects.create(category=cat, sku="EL-MOUSE-01", name_en="Mouse",
                                            price=Decimal("25.00"), stock_quantity=6)
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=2)
        self.order = place_order(self.user, self.address, "card")      # stock 6 -> 4

    def test_cancel_returns_stock_and_refunds(self):
        from .services import cancel_order
        cancel_order(self.order)
        self.mouse.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.mouse.stock_quantity, 6)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.order.payment.status, Payment.Status.REFUNDED)
        self.assertTrue(self.user.notifications.filter(message__contains="refunded").exists())

    def test_cannot_cancel_twice(self):
        from .services import CancelNotAllowedError, cancel_order
        cancel_order(self.order)
        with self.assertRaises(CancelNotAllowedError):
            cancel_order(self.order)
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock_quantity, 6)          # not returned twice

    def test_customer_cannot_cancel_shipped_order(self):
        from .services import CancelNotAllowedError, cancel_order
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.SHIPPED)
        with self.assertRaises(CancelNotAllowedError):
            cancel_order(self.order)
        cancel_order(self.order, by_staff=True)                 # the shop can still do it

    def test_api_cancel_only_own_order(self):
        from rest_framework.test import APIClient
        other = User.objects.create_user("dana", "d@ex.com", "Shop2026!")
        c = APIClient()
        c.force_authenticate(other)
        self.assertEqual(c.post(f"/api/orders/{self.order.pk}/cancel/").status_code, 404)
        c.force_authenticate(self.user)
        r = c.post(f"/api/orders/{self.order.pk}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()["status"], "cancelled")
        self.assertEqual(r.json()["payment_status"], "refunded")



class AssistantTests(TestCase):
    """The simple assistant: FAQ answers, product finder with a budget, order status."""

    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name_en="Electronics", name_ru="Электроника")
        shoes = Category.objects.create(name_en="Shoes", name_ru="Обувь")
        Product.objects.create(category=cat, sku="EL-AIRPD", name_en="Apple Airpods",
                               name_ru="Наушники Apple AirPods", price=Decimal("129.99"), stock_quantity=5)
        Product.objects.create(category=cat, sku="EL-MAX", name_en="AirPods Max",
                               name_ru="Наушники AirPods Max", price=Decimal("549.99"), stock_quantity=5)
        Product.objects.create(category=shoes, sku="SH-AJ1", name_en="Nike Air Jordan 1",
                               name_ru="Кроссовки Nike Air Jordan 1", price=Decimal("149.99"), stock_quantity=5)

    def test_faq_delivery_in_russian(self):
        from .assistant import reply
        self.assertIn("Казахстан", reply("Как работает доставка?", "ru")["text"])

    def test_budget_filter(self):
        from .assistant import reply
        r = reply("наушники до 150$", "ru")
        self.assertEqual([p.sku for p in r["products"]], ["EL-AIRPD"])     # AirPods Max is too expensive

    def test_closest_when_budget_too_small(self):
        from .assistant import reply
        r = reply("кроссовки до 50", "ru")
        self.assertEqual([p.sku for p in r["products"]], ["SH-AJ1"])
        self.assertIn("50", r["text"])

    def test_order_status_needs_login(self):
        from rest_framework.test import APIClient
        r = APIClient().post("/api/assistant/", {"message": "Where is my order?", "lang": "en"}, format="json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("sign in", r.json()["text"].lower())
