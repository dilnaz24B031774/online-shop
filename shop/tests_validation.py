"""
Tester tasks: wrong input, boundaries and access rules (API level).
Run:  python manage.py test shop.tests_validation -v 2
Idea: send BAD data -> the server must answer with a clean 4xx error, never a 500 crash.
"""
from decimal import Decimal

from django.test import TestCase
from rest_framework.test import APIClient

from .models import Address, CartItem, Category, Order, Product, Review, User


class BaseApiTest(TestCase):
    @classmethod
    def setUpTestData(cls):
        cat = Category.objects.create(name_en="Electronics", name_ru="Электроника")
        cls.mouse = Product.objects.create(category=cat, sku="EL-MOUSE-01", name_en="Wireless Mouse",
                                           price=Decimal("25.00"), stock_quantity=6)
        cls.hidden = Product.objects.create(category=cat, sku="EL-OLD-01", name_en="Old Cable",
                                            price=Decimal("5.00"), stock_quantity=3, is_active=False)
        cls.user = User.objects.create_user("aigerim", "aigerim@example.com", "Shop2026!")
        cls.other = User.objects.create_user("dana", "dana@example.com", "Shop2026!")
        cls.address = Address.objects.create(user=cls.user, city="Almaty", street="Abay 10", is_default=True)

    def setUp(self):
        self.client = APIClient()

    def login(self, user=None):
        self.client.force_authenticate(user or self.user)

    def post(self, url, data):
        return self.client.post(url, data, format="json")


class RegistrationTests(BaseApiTest):
    URL = "/api/auth/register/"
    GOOD = {"username": "newuser", "email": "new@example.com", "password": "Shop2026!"}

    def test_valid_registration(self):
        self.assertEqual(self.post(self.URL, self.GOOD).status_code, 201)

    def test_missing_fields(self):
        r = self.post(self.URL, {})
        self.assertEqual(r.status_code, 400)
        for field in ("username", "email", "password"):
            self.assertIn(field, r.json())

    def test_invalid_email(self):
        for bad in ("abc", "abc@", "@mail.com", "a b@mail.com"):
            with self.subTest(email=bad):
                self.assertEqual(self.post(self.URL, {**self.GOOD, "email": bad}).status_code, 400)

    def test_duplicate_username_and_email_any_case(self):
        self.assertEqual(self.post(self.URL, {**self.GOOD, "username": "AIGERIM"}).status_code, 400)
        self.assertEqual(self.post(self.URL, {**self.GOOD, "email": "Aigerim@Example.com"}).status_code, 400)

    def test_password_is_never_returned(self):
        r = self.post(self.URL, self.GOOD)
        self.assertNotIn("Shop2026!", r.content.decode())

    def test_cannot_register_as_admin(self):
        """The client must not be able to choose its own role."""
        self.post(self.URL, {**self.GOOD, "role": "admin", "is_staff": True, "is_superuser": True})
        user = User.objects.get(username="newuser")
        self.assertEqual(user.role, "customer")
        self.assertFalse(user.is_staff or user.is_superuser)


class LoginAndAccessTests(BaseApiTest):
    def test_wrong_password_and_unknown_user(self):
        self.assertEqual(self.post("/api/auth/login/", {"username": "aigerim", "password": "bad"}).status_code, 401)
        self.assertEqual(self.post("/api/auth/login/", {"username": "nobody", "password": "x"}).status_code, 401)

    def test_fake_token_rejected(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer this.is.fake")
        self.assertEqual(self.client.get("/api/cart/").status_code, 401)

    def test_private_endpoints_need_login(self):
        for url in ("/api/cart/", "/api/orders/", "/api/me/", "/api/addresses/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 401)

    def test_public_endpoints_open_for_everyone(self):
        for url in ("/api/categories/", "/api/products/", f"/api/products/{self.mouse.id}/"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_cannot_change_own_role(self):
        self.login()
        self.client.patch("/api/me/", {"role": "admin"}, format="json")
        self.user.refresh_from_db()
        self.assertEqual(self.user.role, "customer")


class CatalogueTests(BaseApiTest):
    def test_inactive_product_is_hidden(self):
        skus = [p["sku"] for p in self.client.get("/api/products/").json()]
        self.assertNotIn("EL-OLD-01", skus)
        self.assertEqual(self.client.get(f"/api/products/{self.hidden.id}/").status_code, 404)

    def test_unknown_product_is_404(self):
        self.assertEqual(self.client.get("/api/products/999999/").status_code, 404)

    def test_search_special_characters_do_not_crash(self):
        for text in ("' OR 1=1 --", "<script>alert(1)</script>", "%", "a" * 500):
            with self.subTest(text=text[:15]):
                self.assertEqual(self.client.get("/api/search/", {"q": text}).status_code, 200)

    def test_search_does_not_leak_other_peoples_orders(self):
        Order.objects.create(user=self.other, shipping_address="Dana secret street 5")
        self.login()
        self.assertEqual(self.client.get("/api/search/?q=secret").json()["orders"], [])


class CartTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.login()

    def add(self, qty, product_id=None):
        return self.post("/api/cart/", {"product_id": product_id or self.mouse.id, "quantity": qty})

    def test_valid_quantity_and_total(self):
        self.assertEqual(self.add(2).json()["total"], "50.00")

    def test_quantity_equal_to_stock_ok_above_stock_rejected(self):
        self.assertEqual(self.add(6).status_code, 200)
        self.assertEqual(self.add(7).status_code, 400)

    def test_quantity_not_a_number(self):
        for bad in ("abc", None, "", "2.5", [1]):
            with self.subTest(quantity=bad):
                self.assertEqual(self.add(bad).status_code, 400)

    def test_zero_and_negative_quantity_remove_item(self):
        for qty in (0, -3):
            with self.subTest(quantity=qty):
                self.add(2)
                self.assertEqual(self.add(qty).status_code, 200)
                self.assertFalse(CartItem.objects.filter(user=self.user).exists())

    def test_unknown_or_inactive_product(self):
        self.assertEqual(self.add(1, product_id=999999).status_code, 404)
        self.assertEqual(self.add(1, product_id=self.hidden.id).status_code, 404)

    def test_carts_are_separate_for_each_user(self):
        self.add(2)
        self.login(self.other)
        self.assertEqual(self.client.get("/api/cart/").json()["items"], [])


class CheckoutTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.login()

    def fill_cart(self, qty=2):
        CartItem.objects.create(user=self.user, product=self.mouse, quantity=qty)

    def checkout(self, **data):
        return self.post("/api/checkout/", {"address_id": self.address.id, "method": "card", **data})

    def test_empty_cart_and_bad_payment_method(self):
        self.assertEqual(self.checkout().status_code, 400)
        self.fill_cart()
        self.assertEqual(self.checkout(method="bitcoin").status_code, 400)

    def test_cannot_use_someone_elses_address(self):
        foreign = Address.objects.create(user=self.other, city="Astana", street="Main 1")
        self.fill_cart()
        self.assertEqual(self.checkout(address_id=foreign.id).status_code, 404)
        self.assertEqual(Order.objects.count(), 0)

    def test_stock_changed_after_adding_to_cart(self):
        self.fill_cart(5)
        Product.objects.filter(pk=self.mouse.pk).update(stock_quantity=2)
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(Order.objects.count(), 0)


class ReviewTests(BaseApiTest):
    def setUp(self):
        super().setUp()
        self.login()
        self.url = f"/api/products/{self.mouse.id}/reviews/"

    def test_rating_boundaries(self):
        for value, expected in ((0, 400), (1, 201), (5, 201), (6, 400), (-1, 400), ("abc", 400), (None, 400)):
            with self.subTest(rating=value):
                Review.objects.all().delete()
                self.assertEqual(self.post(self.url, {"rating": value}).status_code, expected)

    def test_second_review_by_same_user_rejected(self):
        self.post(self.url, {"rating": 5})
        self.assertEqual(self.post(self.url, {"rating": 1}).status_code, 400)

    def test_average_rating(self):
        self.post(self.url, {"rating": 5})
        self.login(self.other)
        self.post(self.url, {"rating": 2})
        self.assertEqual(self.client.get(f"/api/products/{self.mouse.id}/").json()["avg_rating"], 3.5)