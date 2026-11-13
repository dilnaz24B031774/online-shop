"""Demo card payment, payment statuses for card / bank transfer / cash, staff confirmation."""
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from . import payments, services
from .models import Address, CartItem, Category, Notification, Order, Payment, Product, User
from .roles import sync_role_access

GOOD = {"number": "4242 4242 4242 4242", "holder": "AIGERIM K", "exp_month": 12, "exp_year": 2030, "cvc": "123"}
DECLINED = {**GOOD, "number": "4000 0000 0000 0002"}


class PaymentTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.addr = Address.objects.create(user=self.user, city="Almaty", street="Abay 1")
        cat = Category.objects.create(name_en="E", name_ru="Э", name_kk="Э")
        self.p = Product.objects.create(sku="M1", category=cat, name_en="Mouse", name_ru="Мышь", name_kk="Т",
                                        price=Decimal("25"), stock_quantity=10)
        CartItem.objects.create(user=self.user, product=self.p, quantity=2)
        self.c = APIClient()
        self.c.force_authenticate(self.user)

    def checkout(self, method, card=None):
        body = {"address_id": self.addr.id, "method": method}
        if card is not None:
            body["card"] = card
        return self.c.post("/api/checkout/", body, format="json")

    def stock(self):
        return Product.objects.get(pk=self.p.pk).stock_quantity

    # ---------- card checks (nothing is saved for wrong data)
    def test_luhn_and_brand(self):
        self.assertTrue(payments.luhn_ok("4242424242424242"))
        self.assertFalse(payments.luhn_ok("4242424242424241"))
        self.assertEqual(payments.card_brand("5555555555554444"), "mastercard")
        self.assertEqual(payments.card_brand("2200000000000004"), "mir")

    def test_wrong_card_data_saves_nothing(self):
        for field, card in [("number", {**GOOD, "number": "4242 4242 4242 4241"}),
                            ("expiry", {**GOOD, "exp_year": 2020}),
                            ("cvc", {**GOOD, "cvc": "12"}),
                            ("holder", {**GOOD, "holder": ""})]:
            r = self.checkout("card", card)
            self.assertEqual((r.status_code, r.json()["field"]), (400, field))
        self.assertEqual(self.checkout("card").status_code, 400)          # no card at all
        self.assertEqual(Order.objects.count(), 0)
        self.assertEqual(self.stock(), 10)

    # ---------- card approved
    def test_card_paid_keeps_only_last4(self):
        r = self.checkout("card", GOOD)
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()["status"], r.json()["payment_status"]), ("paid", "paid"))
        pay = Payment.objects.get()
        self.assertEqual((pay.card_brand, pay.card_last4), ("visa", "4242"))
        stored = " ".join(str(v) for v in Payment.objects.values().get().values())
        self.assertNotIn("4242424242424242", stored)
        self.assertNotIn("123", pay.provider_reference)
        self.assertEqual(self.stock(), 8)

    # ---------- card declined -> Failed
    def test_declined_card_is_failed_and_keeps_cart_and_stock(self):
        r = self.checkout("card", DECLINED)
        self.assertEqual(r.status_code, 402)
        self.assertEqual(r.json()["order"]["payment_status"], "failed")
        self.assertEqual(Order.objects.get().status, "cancelled")
        self.assertEqual(self.stock(), 10)                                # goods not taken
        self.assertTrue(CartItem.objects.filter(user=self.user).exists())  # can try again
        self.assertIn("отклонена", Notification.objects.get().message_ru)
        self.assertEqual(self.checkout("card", GOOD).status_code, 201)    # second try works

    # ---------- bank transfer -> Pending -> staff confirms -> Paid
    def test_bank_transfer_waits_then_staff_confirms(self):
        order = Order.objects.get(pk=self.checkout("bank_transfer").json()["id"])
        self.assertEqual((order.status, order.payment.status), ("pending", "pending"))
        self.assertIsNone(order.payment.paid_at)
        self.assertEqual(self.stock(), 8)                                 # goods reserved
        with self.assertRaises(services.OrderTransitionError):
            services.fulfill_order(order, Order.Status.SHIPPED)           # not paid yet
        services.confirm_payment(order)
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment.status), ("paid", "paid"))
        with self.assertRaises(services.OrderTransitionError):
            services.confirm_payment(order)                               # only once

    def test_unpaid_transfer_cancel_gives_failed(self):
        order = Order.objects.get(pk=self.checkout("bank_transfer").json()["id"])
        services.cancel_order(order)
        order.refresh_from_db()
        self.assertEqual(order.payment.status, "failed")
        self.assertEqual(self.stock(), 10)

    def test_paid_card_cancel_gives_refunded(self):
        order = Order.objects.get(pk=self.checkout("card", GOOD).json()["id"])
        services.cancel_order(order)
        self.assertEqual(Payment.objects.get().status, "refunded")

    # ---------- cash on delivery -> shipped while pending -> delivered = paid
    def test_cash_on_delivery_paid_when_delivered(self):
        order = Order.objects.get(pk=self.checkout("cash_on_delivery").json()["id"])
        services.fulfill_order(order, Order.Status.SHIPPED)
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment.status), ("shipped", "pending"))
        services.fulfill_order(order, Order.Status.DELIVERED)
        order.refresh_from_db()
        self.assertEqual((order.status, order.payment.status), ("delivered", "paid"))

    # ---------- database rules
    def test_database_rejects_bad_card_columns(self):
        order = Order.objects.get(pk=self.checkout("bank_transfer").json()["id"])
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.filter(pk=order.payment.pk).update(card_last4="4242")   # transfer has no card
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.filter(pk=order.payment.pk).update(method="card", card_last4="42ab")

    # ---------- staff panel button
    def test_staff_confirm_button(self):
        order_id = self.checkout("bank_transfer").json()["id"]
        manager = User.objects.create_user("manager", "m@ex.com", "Shop2026!", role="manager")
        sync_role_access(manager)
        staff = self.client
        staff.force_login(manager)
        self.assertContains(staff.get(f"/staff/orders/{order_id}/"), "Подтвердить оплату")
        staff.post(f"/staff/orders/{order_id}/", {"action": "confirm_payment"})
        self.assertEqual(Order.objects.get(pk=order_id).status, "paid")


class QrInstallmentTests(PaymentTests):
    def test_qr_waits_then_customer_pays_in_app(self):
        r = self.checkout("qr")
        order_id = r.json()["id"]
        self.assertEqual((r.json()["status"], r.json()["payment_status"]), ("pending", "pending"))
        paid = self.c.post(f"/api/orders/{order_id}/pay-qr/").json()
        self.assertEqual((paid["status"], paid["payment_status"]), ("paid", "paid"))
        self.assertEqual(self.c.post(f"/api/orders/{order_id}/pay-qr/").status_code, 400)   # only once

    def test_pay_qr_only_own_qr_orders(self):
        order_id = self.checkout("bank_transfer").json()["id"]
        self.assertEqual(self.c.post(f"/api/orders/{order_id}/pay-qr/").status_code, 404)
        other = User.objects.create_user("dana", "d@ex.com", "Shop2026!")
        c2 = APIClient(); c2.force_authenticate(other)
        CartItem.objects.create(user=self.user, product=self.p, quantity=1)
        qr_id = self.checkout("qr").json()["id"]
        self.assertEqual(c2.post(f"/api/orders/{qr_id}/pay-qr/").status_code, 404)

    def test_installment_paid_with_months(self):
        r = self.c.post("/api/checkout/", {"address_id": self.addr.id, "method": "installment",
                                           "installment_months": 12}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual((r.json()["payment_status"], r.json()["installment_months"]), ("paid", 12))
        self.assertIn("12 ×", Notification.objects.get().message_ru)

    def test_installment_wrong_months(self):
        r = self.c.post("/api/checkout/", {"address_id": self.addr.id, "method": "installment",
                                           "installment_months": 5}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_database_months_rule(self):
        order_id = self.checkout("qr").json()["id"]
        with self.assertRaises(IntegrityError), transaction.atomic():
            Payment.objects.filter(order_id=order_id).update(installment_months=12)   # not an installment
