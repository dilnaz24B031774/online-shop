"""Payment timer, refunds, back-in-stock, saved cards, promo once per customer, Top from real data."""
from datetime import timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from . import services
from .models import (
    Address, CartItem, Category, Notification, Order, OrderItem, Payment, Product, PromoCode, PromoRedemption,
    Refund, SavedCard, StockSubscription, User,
)
from .roles import sync_role_access

CARD = {"number": "4242 4242 4242 4242", "holder": "Aigerim K", "exp_month": 12, "exp_year": 2030, "cvc": "123"}


class Base(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.addr = Address.objects.create(user=self.user, city="Almaty", street="Abay 1")
        cat = Category.objects.create(name_en="Electronics", name_ru="Электроника", name_kk="Электроника")
        self.mouse = Product.objects.create(sku="M1", category=cat, name_en="Mouse", name_ru="Мышь", name_kk="Т",
                                            price=Decimal("30"), stock_quantity=10)
        self.lamp = Product.objects.create(sku="L1", category=cat, name_en="Lamp", name_ru="Лампа", name_kk="Ш",
                                           price=Decimal("20"), stock_quantity=0)
        self.c = APIClient()
        self.c.force_authenticate(self.user)

    def cart(self, product=None, qty=2):
        CartItem.objects.update_or_create(user=self.user, product=product or self.mouse, defaults={"quantity": qty})

    def checkout(self, method="card", **extra):
        body = {"address_id": self.addr.id, "method": method, **extra}
        if method == "card" and "saved_card_id" not in extra and "card" not in extra:
            body["card"] = CARD
        return self.c.post("/api/checkout/", body, format="json")

    def stock(self, p):
        return Product.objects.get(pk=p.pk).stock_quantity


# ------------------------------------------------------------------ 1. payment timer
class PaymentTimerTests(Base):
    def test_qr_order_has_15_minute_deadline(self):
        self.cart()
        r = self.checkout("qr").json()
        left = Payment.objects.get().expires_at - timezone.now()
        self.assertTrue(timedelta(minutes=14) < left <= timedelta(minutes=15))
        self.assertIsNotNone(r["expires_at"])

    def test_expired_order_is_cancelled_and_stock_comes_back(self):
        self.cart()
        order_id = self.checkout("qr").json()["id"]
        self.assertEqual(self.stock(self.mouse), 8)
        Payment.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        orders = self.c.get("/api/orders/").json()                       # lazy check on opening orders
        self.assertEqual((orders[0]["status"], orders[0]["payment_status"]), ("cancelled", "failed"))
        self.assertEqual(orders[0]["failure_reason"], "Payment time is over.")
        self.assertEqual(self.stock(self.mouse), 10)
        self.assertIn("не поступила вовремя", Notification.objects.filter(order_id=order_id).first().message_ru)

    def test_cannot_pay_after_deadline(self):
        self.cart()
        order_id = self.checkout("qr").json()["id"]
        Payment.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        r = self.c.post(f"/api/orders/{order_id}/pay-qr/")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Order.objects.get().status, "cancelled")

    def test_paid_in_time_is_not_cancelled(self):
        self.cart()
        order_id = self.checkout("qr").json()["id"]
        self.c.post(f"/api/orders/{order_id}/pay-qr/")
        Payment.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(services.expire_unpaid_orders(), 0)
        self.assertEqual(Order.objects.get().status, "paid")

    def test_management_command(self):
        from django.core.management import call_command
        self.cart()
        self.checkout("qr")
        Payment.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        call_command("expire_orders", stdout=open("/dev/null", "w"))
        self.assertEqual(Order.objects.get().status, "cancelled")

    @override_settings(PAYMENT_TIMEOUT_MINUTES=1)
    def test_timeout_setting(self):
        self.cart()
        self.checkout("qr")
        self.assertLessEqual(Payment.objects.get().expires_at - timezone.now(), timedelta(minutes=1))


# ------------------------------------------------------------------ 2. refunds
class RefundTests(Base):
    def paid_order(self, qty=3, promo=None):
        self.cart(qty=qty)
        extra = {"promo_code": promo} if promo else {}
        return Order.objects.get(pk=self.checkout("card", **extra).json()["id"])

    def test_partial_refund(self):
        order = self.paid_order(3)                                         # 3 × $30 = $90
        item = order.items.get()
        refund = services.refund_item(order, item.id, 1, "defect")
        self.assertEqual(refund.amount, Decimal("30.00"))
        pay = Payment.objects.get()
        self.assertEqual((pay.status, pay.refunded_amount), ("paid", Decimal("30.00")))
        self.assertEqual(self.stock(self.mouse), 8)                        # 10 - 3 + 1
        self.assertIn("VISA •••• 4242", Notification.objects.filter(order=order).first().message_ru)

    def test_refund_everything_marks_payment_refunded(self):
        order = self.paid_order(2)
        item = order.items.get()
        services.refund_item(order, item.id, 1)
        services.refund_item(order, item.id, 1)
        pay = Payment.objects.get()
        self.assertEqual((pay.status, pay.refunded_amount), ("refunded", pay.amount))
        with self.assertRaises(services.RefundError):
            services.refund_item(order, item.id, 1)

    def test_refund_respects_promo_discount(self):
        PromoCode.objects.create(code="WELCOME10", discount_percent=10)
        order = self.paid_order(2, promo="WELCOME10")                       # 60 - 6 = 54
        refund = services.refund_item(order, order.items.get().id, 1)
        self.assertEqual(refund.amount, Decimal("27.00"))

    def test_cannot_refund_more_than_bought_or_unpaid(self):
        order = self.paid_order(2)
        with self.assertRaises(services.RefundError):
            services.refund_item(order, order.items.get().id, 3)
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=1)
        unpaid = Order.objects.get(pk=self.checkout("qr").json()["id"])
        with self.assertRaises(services.RefundError):
            services.refund_item(unpaid, unpaid.items.get().id, 1)

    def test_database_rules(self):
        order = self.paid_order(2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            OrderItem.objects.filter(order=order).update(refunded_quantity=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.filter(order=order).update(refunded_amount=Decimal("1000"))

    def test_cancel_after_partial_refund_returns_only_the_rest(self):
        order = self.paid_order(3)
        services.refund_item(order, order.items.get().id, 1)
        services.cancel_order(order)
        pay = Payment.objects.get()
        self.assertEqual((pay.status, pay.refunded_amount), ("refunded", Decimal("90.00")))
        self.assertEqual(self.stock(self.mouse), 10)                       # not 11

    def test_staff_refund_form_and_customer_sees_it(self):
        order = self.paid_order(2)
        manager = User.objects.create_user("manager", "m@ex.com", "Shop2026!", role="manager")
        sync_role_access(manager)
        self.client.force_login(manager)
        page = self.client.get(f"/staff/orders/{order.pk}/")
        self.assertContains(page, "Вернуть")
        self.client.post(f"/staff/orders/{order.pk}/", {"action": "refund", "item_id": order.items.get().id,
                                                         "quantity": 1, "reason": "wrong_item"})
        self.assertEqual(Refund.objects.get().created_by, manager)
        data = self.c.get("/api/orders/").json()[0]
        self.assertEqual((data["refunded_amount"], data["refunds"][0]["quantity"]), ("30.00", 1))


# ------------------------------------------------------------------ 3. back in stock
class BackInStockTests(Base):
    def test_subscribe_only_when_out_of_stock(self):
        self.assertEqual(self.c.post(f"/api/products/{self.lamp.id}/notify-me/").status_code, 201)
        self.assertEqual(self.c.post(f"/api/products/{self.mouse.id}/notify-me/").status_code, 400)
        self.assertEqual(self.c.get("/api/stock-alerts/").json()["product_ids"], [self.lamp.id])
        self.c.delete(f"/api/products/{self.lamp.id}/notify-me/")
        self.assertEqual(self.c.get("/api/stock-alerts/").json()["product_ids"], [])

    def test_restock_by_manager_sends_notification_once(self):
        self.c.post(f"/api/products/{self.lamp.id}/notify-me/")
        self.c.post(f"/api/products/{self.lamp.id}/notify-me/")             # twice -> still one
        with self.captureOnCommitCallbacks(execute=True):
            self.lamp.stock_quantity = 5
            self.lamp.save()
        n = Notification.objects.get(user=self.user)
        self.assertIn("Снова в наличии", n.message_ru)
        self.assertEqual(n.link, f"/product/{self.lamp.id}")
        self.assertIsNotNone(StockSubscription.objects.get().notified_at)

    def test_cancelled_order_returns_last_item_and_notifies(self):
        other = User.objects.create_user("dana", "d@ex.com", "Shop2026!")
        self.mouse.stock_quantity = 1
        self.mouse.save()
        self.cart(qty=1)
        order = Order.objects.get(pk=self.checkout("card").json()["id"])    # takes the last mouse
        StockSubscription.objects.create(user=other, product=self.mouse)
        services.cancel_order(order)
        self.assertTrue(Notification.objects.filter(user=other, message_ru__startswith="Снова в наличии").exists())

    def test_one_active_subscription_rule_in_database(self):
        StockSubscription.objects.create(user=self.user, product=self.lamp)
        with self.assertRaises(IntegrityError), transaction.atomic():
            StockSubscription.objects.create(user=self.user, product=self.lamp)


# ------------------------------------------------------------------ 4. saved cards
class SavedCardTests(Base):
    def test_save_card_keeps_only_token_and_last4(self):
        self.cart()
        self.checkout("card", card=CARD, save_card=True)
        card = SavedCard.objects.get()
        self.assertTrue(card.token.startswith("tok_"))
        self.assertEqual((card.brand, card.last4, card.exp_month, card.exp_year), ("visa", "4242", 12, 2030))
        stored = " ".join(str(v) for v in SavedCard.objects.values().get().values())
        self.assertNotIn("4242424242424242", stored)
        listed = self.c.get("/api/cards/").json()["cards"][0]
        self.assertNotIn("token", listed)

    def test_pay_with_saved_card_needs_cvc(self):
        self.cart()
        self.checkout("card", card=CARD, save_card=True)
        card = SavedCard.objects.get()
        self.cart()
        bad = self.checkout("card", saved_card_id=card.id, cvc="1")
        self.assertEqual(bad.json()["field"], "cvc")
        ok = self.checkout("card", saved_card_id=card.id, cvc="321")
        self.assertEqual(ok.status_code, 201)
        self.assertEqual(Payment.objects.order_by("-id").first().saved_card, card)

    def test_only_recent_card_users_see_cards(self):
        SavedCard.objects.create(user=self.user, token="tok_old", brand="visa", last4="1111", holder="A",
                                 exp_month=1, exp_year=2031, last_used_at=timezone.now() - timedelta(days=200))
        self.assertEqual(self.c.get("/api/cards/").json()["cards"], [])
        self.cart()
        r = self.checkout("card", saved_card_id=SavedCard.objects.get().id, cvc="123")
        self.assertEqual(r.json()["field"], "saved_card")

    def test_foreign_card_cannot_be_used_or_deleted(self):
        other = User.objects.create_user("dana", "d@ex.com", "Shop2026!")
        card = SavedCard.objects.create(user=other, token="tok_x", brand="visa", last4="2222", holder="D",
                                        exp_month=1, exp_year=2031, last_used_at=timezone.now())
        self.cart()
        self.assertEqual(self.checkout("card", saved_card_id=card.id, cvc="123").status_code, 400)
        self.assertEqual(self.c.delete(f"/api/cards/{card.id}/").status_code, 404)

    def test_declined_card_is_not_saved(self):
        self.cart()
        self.checkout("card", card={**CARD, "number": "4000 0000 0000 0002"}, save_card=True)
        self.assertFalse(SavedCard.objects.exists())


# ------------------------------------------------------------------ 5. promo code once per customer
class PromoOnceTests(Base):
    def setUp(self):
        super().setUp()
        PromoCode.objects.create(code="WELCOME10", discount_percent=10)

    def test_second_use_is_refused(self):
        self.cart()
        self.assertEqual(self.checkout("card", promo_code="WELCOME10").status_code, 201)
        self.cart()
        r = self.checkout("card", promo_code="WELCOME10")
        self.assertEqual((r.status_code, r.json()["code"]), (400, "already_used"))
        check = self.c.post("/api/promo/check/", {"code": "welcome10"}, format="json")
        self.assertEqual(check.json()["code"], "already_used")

    def test_other_customer_can_use_it(self):
        self.cart()
        self.checkout("card", promo_code="WELCOME10")
        dana = User.objects.create_user("dana", "d@ex.com", "Shop2026!")
        services.check_promo("WELCOME10", Decimal("50"), user=dana)        # no error

    def test_cancel_gives_the_code_back(self):
        self.cart()
        order = Order.objects.get(pk=self.checkout("card", promo_code="WELCOME10").json()["id"])
        services.cancel_order(order)
        self.cart()
        self.assertEqual(self.checkout("card", promo_code="WELCOME10").status_code, 201)

    def test_database_unique_rule(self):
        self.cart()
        order = Order.objects.get(pk=self.checkout("card", promo_code="WELCOME10").json()["id"])
        other_order = Order.objects.create(user=self.user, shipping_address="A")
        with self.assertRaises(IntegrityError), transaction.atomic():
            PromoRedemption.objects.create(user=self.user, promo=order.promo_code, order=other_order)


# ------------------------------------------------------------------ 6. top from real purchases
class TopTests(Base):
    def buy(self, product, qty, days_ago=0, demo=False, status="paid"):
        o = Order.objects.create(user=self.user, shipping_address="A", status=status, is_demo=demo)
        OrderItem.objects.create(order=o, product=product, quantity=qty, unit_price=product.price)
        Order.objects.filter(pk=o.pk).update(created_at=timezone.now() - timedelta(days=days_ago))
        return o

    def test_hits_ignore_demo_unpaid_and_returned(self):
        self.buy(self.mouse, 2)
        self.buy(self.lamp, 50, demo=True)                    # demo - not counted
        self.buy(self.lamp, 40, status="pending")            # not paid - not counted
        r = self.c.get("/api/top/?kind=hits&period=all").json()["items"]
        self.assertEqual([(i["product"]["sku"], i["units"]) for i in r], [("M1", 2)])
        OrderItem.objects.filter(product=self.mouse).update(refunded_quantity=2)
        self.assertEqual(self.c.get("/api/top/?kind=hits&period=all").json()["items"], [])

    def test_hits_period(self):
        self.buy(self.mouse, 3, days_ago=40)
        self.assertEqual(self.c.get("/api/top/?kind=hits&period=30").json()["items"], [])
        self.assertEqual(len(self.c.get("/api/top/?kind=hits&period=90").json()["items"]), 1)

    def test_trends_growth(self):
        self.buy(self.mouse, 1, days_ago=10)
        self.buy(self.mouse, 4, days_ago=2)                   # 1 -> 4 = +300 %
        self.buy(self.lamp, 2, days_ago=1)                    # new this week
        items = self.c.get("/api/top/?kind=trends").json()["items"]
        self.assertEqual(items[0]["product"]["sku"], "M1")
        self.assertEqual((items[0]["units"], items[0]["prev_units"], items[0]["growth"]), (4, 1, 300))
        self.assertIsNone(items[1]["growth"])

    def test_new_products_first(self):
        items = self.c.get("/api/top/?kind=new").json()["items"]
        self.assertEqual(items[0]["product"]["sku"], "L1")

    def test_home_best_sellers_real_only(self):
        self.buy(self.lamp, 9, demo=True)
        self.assertEqual(self.c.get("/api/products/best-sellers/").json(), [])


# ------------------------------------------------------------------ 7. real QR scanned with a phone
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile Safari/604.1"


class QrScanTests(Base):
    def qr_order(self):
        self.cart()
        data = self.checkout("qr").json()
        return data["id"], data["qr_token"]

    def test_qr_order_gets_secret_token(self):
        order_id, token = self.qr_order()
        self.assertGreaterEqual(len(token), 30)
        phone = APIClient()                                              # not logged in
        info = phone.get(f"/api/qr/{token}/").json()
        self.assertEqual((info["order_id"], info["amount"], info["state"]), (order_id, "60.00", "pending"))

    def test_phone_pays_and_order_becomes_paid(self):
        order_id, token = self.qr_order()
        r = APIClient().post(f"/api/qr/{token}/pay/", HTTP_USER_AGENT=IPHONE)
        self.assertEqual((r.status_code, r.json()["state"], r.json()["paid_device"]), (200, "paid", "iPhone · Safari"))
        order = self.c.get("/api/orders/").json()[0]
        self.assertEqual((order["status"], order["payment_status"], order["qr_token"]), ("paid", "paid", None))
        self.assertEqual(order["qr_paid_device"], "iPhone · Safari")

    def test_token_works_only_once(self):
        _, token = self.qr_order()
        APIClient().post(f"/api/qr/{token}/pay/", HTTP_USER_AGENT=IPHONE)
        again = APIClient().post(f"/api/qr/{token}/pay/")
        self.assertEqual((again.status_code, again.json()["state"]), (409, "paid"))

    def test_expired_token_cannot_pay(self):
        _, token = self.qr_order()
        Payment.objects.update(expires_at=timezone.now() - timedelta(seconds=1))
        from .models import QrPayment
        QrPayment.objects.update(expires_at=timezone.now() - timedelta(seconds=1),
                                 created_at=timezone.now() - timedelta(minutes=16))
        r = APIClient().post(f"/api/qr/{token}/pay/", HTTP_USER_AGENT=IPHONE)
        self.assertEqual((r.status_code, r.json()["state"]), (409, "expired"))
        self.assertEqual(Order.objects.get().status, "cancelled")

    def test_unknown_token(self):
        self.assertEqual(APIClient().get("/api/qr/nope/").status_code, 404)
        self.assertEqual(APIClient().post("/api/qr/nope/pay/").status_code, 404)

    def test_token_hidden_from_other_customers(self):
        self.qr_order()
        other = APIClient()
        other.force_authenticate(User.objects.create_user("dana", "d@ex.com", "Shop2026!"))
        self.assertEqual(other.get("/api/orders/").json(), [])
