"""Bonus programme: treats from paid orders, feeding the mascots, merch gifts."""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from . import services
from .models import Address, BonusFeeding, CartItem, Category, GiftClaim, Notification, Order, Payment, Product, User


class BonusTests(TestCase):
    def setUp(self):
        self.buyer = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.addr = Address.objects.create(user=self.buyer, city="Almaty", street="Abay 1", is_default=True)
        cat = Category.objects.create(name_en="Electronics", name_ru="Электроника", name_kk="Электроника")
        self.phone = Product.objects.create(sku="P1", category=cat, name_en="Phone", name_ru="Телефон", name_kk="Т",
                                            price=Decimal("125"), stock_quantity=50)
        self.api = APIClient()
        self.api.force_authenticate(self.buyer)

    def buy(self, quantity=1, method="card"):
        CartItem.objects.create(user=self.buyer, product=self.phone, quantity=quantity)
        return services.place_order(self.buyer, self.addr, method)

    def state(self):
        return self.api.get("/api/bonus/").json()

    def feed(self, character, treat, quantity):
        return self.api.post("/api/bonus/feed/", {"character": character, "treat": treat, "quantity": quantity},
                             format="json")

    def test_paid_order_earns_kurt_and_kozhe(self):
        self.buy()                                                    # $125 paid by card
        state = self.state()
        self.assertEqual(state["earned"], {"kurt": 12, "kozhe": 2})
        self.assertEqual(state["available"], {"kurt": 12, "kozhe": 2})

    def test_unpaid_and_cancelled_orders_earn_nothing(self):
        order = self.buy(method="bank_transfer")                      # waits for payment
        self.assertEqual(self.state()["earned"], {"kurt": 0, "kozhe": 0})
        services.cancel_order(order)
        self.assertEqual(self.state()["earned"], {"kurt": 0, "kozhe": 0})

    def test_feeding_moves_points_to_one_mascot(self):
        self.buy()
        self.assertEqual(self.feed("aisulu", "kozhe", 2).status_code, 200)
        state = self.feed("aisulu", "kurt", 3).json()
        aisulu = next(c for c in state["characters"] if c["id"] == "aisulu")
        altai = next(c for c in state["characters"] if c["id"] == "altai")
        self.assertEqual((aisulu["points"], altai["points"]), (13, 0))        # 2*5 + 3
        self.assertEqual(state["available"], {"kurt": 9, "kozhe": 0})
        self.assertTrue(aisulu["gifts"][0]["unlocked"])                         # 10 points
        self.assertEqual(aisulu["next_goal"], 30)

    def test_cannot_feed_more_than_earned_or_bad_values(self):
        self.buy()
        self.assertEqual(self.feed("altai", "kozhe", 3).json()["detail"], "not_enough_treats")
        for bad in ({"character": "boss", "treat": "kurt", "quantity": 1},
                    {"character": "altai", "treat": "cake", "quantity": 1},
                    {"character": "altai", "treat": "kurt", "quantity": 0}):
            self.assertEqual(self.api.post("/api/bonus/feed/", bad, format="json").status_code, 400)
        self.assertFalse(BonusFeeding.objects.exists())

    def test_claim_gift_once_and_staff_send_it(self):
        self.buy()
        self.feed("altai", "kozhe", 2)
        locked = self.api.post("/api/bonus/claim/", {"gift": "altai_mug"}, format="json")
        self.assertEqual(locked.json()["detail"], "gift_locked")                 # needs 30 points
        ok = self.api.post("/api/bonus/claim/", {"gift": "altai_badge"}, format="json")
        self.assertEqual(ok.status_code, 201)
        claim = GiftClaim.objects.get()
        self.assertEqual((claim.gift, claim.address), ("altai_badge", "Almaty, Abay 1"))
        again = self.api.post("/api/bonus/claim/", {"gift": "altai_badge"}, format="json")
        self.assertEqual(again.status_code, 409)

        staff = User.objects.create_superuser("boss", "boss@ex.com", "Shop2026!")
        self.client.force_login(staff)
        page = self.client.get("/staff/gifts/")
        self.assertContains(page, "Значок с Алтаем")
        self.client.post("/staff/gifts/", {"claim": claim.pk})
        claim.refresh_from_db()
        self.assertEqual(claim.status, "sent")
        self.assertTrue(Notification.objects.filter(user=self.buyer, link="/bonus").exists())
        self.assertEqual(self.state()["characters"][1]["gifts"][0]["status"], "sent")

    def test_refund_takes_unspent_treats_back(self):
        order = self.buy()
        Payment.objects.filter(order=order).update(refunded_amount=Decimal("100"))
        self.assertEqual(self.state()["earned"], {"kurt": 2, "kozhe": 0})        # $25 left

    def test_customers_only_and_staff_page_closed_to_customers(self):
        self.assertEqual(APIClient().get("/api/bonus/").status_code, 401)
        self.client.force_login(self.buyer)
        self.assertNotEqual(self.client.get("/staff/gifts/").status_code, 200)
