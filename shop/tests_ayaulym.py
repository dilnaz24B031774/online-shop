"""
Integration tests — Oishy Ayaulym (Testing, Analytics & Integration)

These tests check the shop the way a user works with it: through the REST API
(the same requests the Angular website sends) and then in the database.

Run only these tests:   python3 manage.py test shop.tests_ayaulym
Run all tests:          python3 manage.py test shop
"""
from decimal import Decimal

from rest_framework.test import APIClient
from django.test import TestCase

from .models import Address, CartItem, Category, Order, Payment, Product, Review, User

TEST_CARD = {"number": "4242 4242 4242 4242", "holder": "AIGERIM K", "exp_month": 12, "exp_year": 2030, "cvc": "123"}


class BaseShopTest(TestCase):
    """Common test data: one customer, one address, two products."""

    def setUp(self):
        self.user = User.objects.create_user("ayaulym", "ayaulym@example.com", "Shop2026!")
        self.address = Address.objects.create(user=self.user, city="Almaty", street="Abay Ave 1",
                                              is_default=True)
        sports = Category.objects.create(name_en="Sports", name_ru="Спорт", name_kk="Спорт")
        self.glove = Product.objects.create(category=sports, sku="SP-GLOVE", name_en="Baseball Glove",
                                            name_ru="Бейсбольная перчатка", price=Decimal("24.99"),
                                            stock_quantity=0)                 # empty stock
        self.ball = Product.objects.create(category=sports, sku="SP-FOOTB", name_en="Football",
                                           name_ru="Футбольный мяч", name_kk="Футбол добы",
                                           price=Decimal("17.99"), stock_quantity=5)
        self.client = APIClient()            # not logged in
        self.auth = APIClient()              # logged in as the customer
        self.auth.force_authenticate(self.user)

    def checkout(self, client=None):
        client = client or self.auth
        return client.post("/api/checkout/", {"address_id": self.address.id, "method": "card", "card": TEST_CARD},
                           format="json")


# ----------------------------------------------------------------------------
# 1. Empty stock
# ----------------------------------------------------------------------------
class EmptyStockTests(BaseShopTest):

    def test_cannot_add_empty_product_to_cart(self):
        r = self.auth.post("/api/cart/", {"product_id": self.glove.id, "quantity": 1}, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("Only 0 left", r.json()["detail"])
        self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_checkout_fails_when_stock_became_zero(self):
        # the product was in the cart, then somebody else bought the last item
        CartItem.objects.create(user=self.user, product=self.glove, quantity=1)
        r = self.checkout()
        self.assertEqual(r.status_code, 400)
        self.assertIn("Not enough stock", r.json()["detail"])
        self.assertEqual(Order.objects.count(), 0)                         # no order
        self.assertTrue(CartItem.objects.filter(user=self.user).exists())  # cart is kept

    def test_buying_all_items_makes_stock_zero(self):
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 5}, format="json")
        self.assertEqual(self.checkout().status_code, 201)
        self.ball.refresh_from_db()
        self.assertEqual(self.ball.stock_quantity, 0)

    def test_cancel_brings_stock_back(self):
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 5}, format="json")
        order_id = self.checkout().json()["id"]
        r = self.auth.post(f"/api/orders/{order_id}/cancel/")
        self.assertEqual(r.status_code, 200)
        self.ball.refresh_from_db()
        self.assertEqual(self.ball.stock_quantity, 5)
        self.assertEqual(Payment.objects.get(order_id=order_id).status, Payment.Status.REFUNDED)

    def test_assistant_does_not_offer_empty_products(self):
        r = self.client.post("/api/assistant/", {"message": "ball", "lang": "en"}, format="json")
        skus = [p["sku"] for p in r.json()["products"]]
        self.assertIn("SP-FOOTB", skus)
        self.assertNotIn("SP-GLOVE", skus)


# ----------------------------------------------------------------------------
# 2. Password edge cases (on the registration page)
# ----------------------------------------------------------------------------
class PasswordEdgeCaseTests(BaseShopTest):

    def register(self, password, username="newuser"):
        return self.client.post("/api/auth/register/", {
            "username": username, "email": f"{username}@example.com", "password": password,
        }, format="json")

    def assertRefused(self, password):
        r = self.register(password)
        self.assertEqual(r.status_code, 400, f"password {password!r} should be refused")
        self.assertIn("password", r.json())
        self.assertFalse(User.objects.filter(username="newuser").exists())

    def test_only_spaces(self):
        self.assertRefused("        ")

    def test_seven_characters(self):
        self.assertRefused("Shop202")

    def test_same_as_username(self):
        self.assertRefused("Newuser2026")

    def test_common_password(self):
        self.assertRefused("Password1")

    def test_cyrillic_strong_password_is_accepted(self):
        r = self.register("Магазин2026!")
        self.assertEqual(r.status_code, 201)
        user = User.objects.get(username="newuser")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))   # only the hash is saved
        self.assertIn("access", r.json())                             # JWT token is returned

    def test_same_email_twice_is_refused(self):
        r = self.client.post("/api/auth/register/", {
            "username": "other", "email": "ayaulym@example.com", "password": "Shop2026!",
        }, format="json")
        self.assertEqual(r.status_code, 400)
        self.assertIn("email", r.json())


# ----------------------------------------------------------------------------
# 3. Access: without login and to other people's data
# ----------------------------------------------------------------------------
class AccessTests(BaseShopTest):

    def test_private_pages_need_login(self):
        for url in ("/api/cart/", "/api/orders/", "/api/me/", "/api/addresses/"):
            self.assertEqual(self.client.get(url).status_code, 401, url)

    def test_checkout_without_login(self):
        self.assertEqual(self.checkout(self.client).status_code, 401)

    def test_wrong_password_gives_no_token(self):
        r = self.client.post("/api/auth/login/", {"username": "ayaulym", "password": "wrong"},
                             format="json")
        self.assertEqual(r.status_code, 401)
        self.assertNotIn("access", r.json())

    def test_login_token_opens_private_pages(self):
        r = self.client.post("/api/auth/login/", {"username": "ayaulym", "password": "Shop2026!"},
                             format="json")
        token = r.json()["access"]
        c = APIClient()
        c.credentials(HTTP_AUTHORIZATION="Bearer " + token)
        self.assertEqual(c.get("/api/orders/").status_code, 200)

    def test_cannot_use_other_customers_address(self):
        other = User.objects.create_user("dana", "dana@example.com", "Shop2026!")
        other_address = Address.objects.create(user=other, city="Astana", street="Mira 9")
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 1}, format="json")
        r = self.auth.post("/api/checkout/", {"address_id": other_address.id, "method": "card", "card": TEST_CARD},
                           format="json")
        self.assertEqual(r.status_code, 404)
        self.assertEqual(Order.objects.count(), 0)

    def test_customer_sees_only_own_orders_in_search(self):
        other = User.objects.create_user("dana", "dana@example.com", "Shop2026!")
        Order.objects.create(user=other, shipping_address="Almaty, secret street", total_amount=10)
        r = self.auth.get("/api/search/?q=secret")
        self.assertEqual(r.json()["orders"], [])


# ----------------------------------------------------------------------------
# 4. Checkout and cart rules
# ----------------------------------------------------------------------------
class CheckoutRulesTests(BaseShopTest):

    def test_empty_cart_cannot_be_ordered(self):
        r = self.checkout()
        self.assertEqual(r.status_code, 400)
        self.assertIn("empty", r.json()["detail"])

    def test_unknown_payment_method(self):
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 1}, format="json")
        r = self.auth.post("/api/checkout/", {"address_id": self.address.id, "method": "bitcoin"},
                           format="json")
        self.assertEqual(r.status_code, 400)

    def test_quantity_zero_removes_product_from_cart(self):
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 2}, format="json")
        r = self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 0}, format="json")
        self.assertEqual(r.json()["count"], 0)

    def test_order_keeps_price_at_purchase_time(self):
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 1}, format="json")
        order_id = self.checkout().json()["id"]
        Product.objects.filter(pk=self.ball.pk).update(price=Decimal("99.00"))   # price changes later
        order = self.auth.get("/api/orders/").json()[0]
        self.assertEqual(order["id"], order_id)
        self.assertEqual(order["items"][0]["unit_price"], "17.99")
        self.assertEqual(order["total_amount"], "17.99")


# ----------------------------------------------------------------------------
# 5. Reviews and search
# ----------------------------------------------------------------------------
class ReviewAndSearchTests(BaseShopTest):

    def test_second_review_for_same_product_is_refused(self):
        self.auth.post("/api/cart/", {"product_id": self.ball.id, "quantity": 1}, format="json")
        self.assertEqual(self.checkout().status_code, 201)
        url = f"/api/products/{self.ball.id}/reviews/"
        self.assertEqual(self.auth.post(url, {"rating": 5, "comment": "Good"}, format="json").status_code, 201)
        self.assertEqual(self.auth.post(url, {"rating": 4, "comment": "Again"}, format="json").status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_rating_six_is_refused(self):
        r = self.auth.post(f"/api/products/{self.ball.id}/reviews/", {"rating": 6}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_search_in_three_languages(self):
        for word in ("football", "футбольный", "футбол добы"):
            skus = [p["sku"] for p in self.client.get(f"/api/search/?q={word}").json()["products"]]
            self.assertIn("SP-FOOTB", skus, word)
