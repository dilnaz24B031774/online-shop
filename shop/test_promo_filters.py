"""Promo codes and catalogue filters."""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import Address, CartItem, Category, Order, Product, PromoCode, Review, User

TEST_CARD = {"number": "4242 4242 4242 4242", "holder": "AIGERIM K", "exp_month": 12, "exp_year": 2030, "cvc": "123"}


class PromoFilterBase(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.cat = Category.objects.create(name_en="Electronics", name_ru="Электроника", name_kk="Электроника")
        self.mouse = Product.objects.create(sku="M1", category=self.cat, name_en="Mouse", name_ru="Мышь",
                                            name_kk="Тінтуір", price=Decimal("25"), stock_quantity=10, brand="Logi")
        self.phone = Product.objects.create(sku="P1", category=self.cat, name_en="Phone", name_ru="Телефон",
                                            name_kk="Телефон", price=Decimal("500"), stock_quantity=0, brand="Apple")
        self.lamp = Product.objects.create(sku="L1", category=self.cat, name_en="Lamp", name_ru="Лампа",
                                           name_kk="Шам", price=Decimal("80"), stock_quantity=3, brand="Apple")
        self.address = Address.objects.create(user=self.user, city="Almaty", street="Abay 1")
        self.c = APIClient()
        self.c.force_authenticate(self.user)


class PromoCodeTests(PromoFilterBase):
    def test_code_gives_discount_and_counts_use(self):
        PromoCode.objects.create(code="welcome10", discount_percent=10)
        CartItem.objects.create(user=self.user, product=self.lamp, quantity=1)       # $80
        order = services.place_order(self.user, self.address, "card", promo_code="Welcome10")
        self.assertEqual(order.discount_amount, Decimal("8.00"))
        self.assertEqual(order.total_amount, Decimal("72.00"))
        self.assertEqual(order.payment.amount, Decimal("72.00"))
        self.assertEqual(PromoCode.objects.get().used_count, 1)

    def test_bad_code_rolls_back_whole_order(self):
        CartItem.objects.create(user=self.user, product=self.lamp, quantity=1)
        with self.assertRaises(services.PromoCodeError):
            services.place_order(self.user, self.address, "card", promo_code="NOPE")
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(Product.objects.get(pk=self.lamp.pk).stock_quantity, 3)    # stock not touched
        self.assertTrue(CartItem.objects.exists())                                   # cart kept

    def test_expired_used_up_and_min_order(self):
        now = timezone.now()
        PromoCode.objects.create(code="OLD", discount_percent=10, valid_until=now - timedelta(days=1),
                                 valid_from=now - timedelta(days=5))
        PromoCode.objects.create(code="ONCE", discount_percent=10, max_uses=1, used_count=1)
        PromoCode.objects.create(code="BIG", discount_percent=10, min_order_amount=Decimal("100"))
        for code in ("OLD", "ONCE", "BIG"):
            with self.assertRaises(services.PromoCodeError):
                services.check_promo(code, Decimal("80"))

    def test_cancel_returns_the_use(self):
        PromoCode.objects.create(code="SAUDA5", discount_percent=5)
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=1)
        order = services.place_order(self.user, self.address, "card", promo_code="SAUDA5")
        services.cancel_order(order)
        self.assertEqual(PromoCode.objects.get().used_count, 0)

    def test_database_rejects_wrong_percent(self):
        from django.db import IntegrityError, transaction
        with self.assertRaises(IntegrityError), transaction.atomic():
            PromoCode.objects.create(code="FREE", discount_percent=100)

    def test_api_check_and_checkout(self):
        PromoCode.objects.create(code="WELCOME10", discount_percent=10)
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=2)      # $50
        r = self.c.post("/api/promo/check/", {"code": "welcome10"}, format="json").json()
        self.assertEqual((r["discount"], r["total"]), ("5.00", "45.00"))
        self.assertEqual(self.c.post("/api/promo/check/", {"code": "x"}, format="json").status_code, 400)
        r = self.c.post("/api/checkout/", {"address_id": self.address.id, "method": "card", "card": TEST_CARD,
                                           "promo_code": "WELCOME10"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["promo"], "WELCOME10")
        self.assertEqual(r.json()["total_amount"], "45.00")


class FilterTests(PromoFilterBase):
    def ids(self, query):
        return [p["sku"] for p in APIClient().get("/api/products/" + query).json()]

    def test_price_brand_stock(self):
        self.assertEqual(sorted(self.ids("?min_price=50&max_price=600")), ["L1", "P1"])
        self.assertEqual(sorted(self.ids("?brand=Apple")), ["L1", "P1"])
        self.assertEqual(self.ids("?brand=Apple&in_stock=1"), ["L1"])
        self.assertEqual(self.ids("?sort=price"), ["M1", "L1", "P1"])

    def test_rating_filter_and_sort(self):
        other = User.objects.create_user("dana", "d@ex.com", "Shop2026!")
        Review.objects.create(user=self.user, product=self.lamp, rating=5)
        Review.objects.create(user=other, product=self.mouse, rating=3)
        self.assertEqual(self.ids("?min_rating=4"), ["L1"])
        self.assertEqual(self.ids("?sort=rating")[:2], ["L1", "M1"])

    def test_filter_options(self):
        data = APIClient().get("/api/products/filters/").json()
        self.assertEqual([b["brand"] for b in data["brands"]], ["Apple", "Logi"])
        self.assertEqual((data["min_price"], data["max_price"]), ("25.00", "500.00"))
