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

    def test_buying_last_items_sets_stock_to_zero(self):
        self.fill_cart(6)
        self.assertEqual(self.checkout().status_code, 201)
        self.mouse.refresh_from_db()
        self.assertEqual(self.mouse.stock_quantity, 0)

    def test_stock_changed_after_adding_to_cart(self):
        self.fill_cart(5)
        Product.objects.filter(pk=self.mouse.pk).update(stock_quantity=2)
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_price_change_does_not_change_old_order(self):
        self.fill_cart(1)
        order_id = self.checkout().json()["id"]
        Product.objects.filter(pk=self.mouse.pk).update(price=Decimal("99.00"))
        self.assertEqual(Order.objects.get(pk=order_id).total_amount, Decimal("25.00"))

    def test_double_checkout_creates_only_one_order(self):
        self.fill_cart()
        self.assertEqual(self.checkout().status_code, 201)
        self.assertEqual(self.checkout().status_code, 400)
        self.assertEqual(Order.objects.count(), 1)


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


class BugHuntTests(BaseApiTest):
    """
    Tests that look for WRONG behaviour of the shop. They fail now = a bug is found.
    Each docstring says what the shop does wrong and what it should do.
    """

    def test_fractional_quantity_must_be_rejected(self):
        """BUG: quantity 2.5 (or true) is silently turned into 2 (or 1). It should be 400."""
        self.login()
        for bad in (2.5, True):
            with self.subTest(quantity=bad):
                r = self.post("/api/cart/", {"product_id": self.mouse.id, "quantity": bad})
                self.assertEqual(r.status_code, 400)

    def test_product_of_hidden_category_must_not_be_shown(self):
        """BUG: category is switched off, but its products are still in the catalogue."""
        hidden_cat = Category.objects.create(name_en="Hidden", is_active=False)
        Product.objects.create(category=hidden_cat, sku="HID-1", name_en="Secret item",
                               price=Decimal("10.00"), stock_quantity=5)
        skus = [p["sku"] for p in self.client.get("/api/products/").json()]
        self.assertNotIn("HID-1", skus)

    def test_product_of_hidden_category_cannot_be_bought(self):
        """BUG: a product from a switched-off category can still be added to the cart."""
        self.login()
        hidden_cat = Category.objects.create(name_en="Hidden", is_active=False)
        item = Product.objects.create(category=hidden_cat, sku="HID-2", name_en="Secret item",
                                      price=Decimal("10.00"), stock_quantity=5)
        r = self.post("/api/cart/", {"product_id": item.id, "quantity": 1})
        self.assertNotEqual(r.status_code, 200)

    def test_search_finds_kazakh_description(self):
        """BUG: search looks in English and Russian descriptions, but not in Kazakh."""
        Product.objects.create(category=self.mouse.category, sku="EL-KK", name_en="Pad",
                               description_kk="жұмсақ төсеніш", price=Decimal("3.00"), stock_quantity=2)
        found = self.client.get("/api/search/", {"q": "жұмсақ"}).json()["products"]
        self.assertEqual([p["sku"] for p in found], ["EL-KK"])

    def test_unpaid_payment_methods_must_not_be_marked_paid(self):
        """BUG: cash on delivery and bank transfer are 'paid' at once. They should wait for the money."""
        self.login()
        for method in ("bank_transfer", "cash_on_delivery"):
            with self.subTest(method=method):
                CartItem.objects.all().delete()
                CartItem.objects.create(user=self.user, product=self.mouse, quantity=1)
                r = self.post("/api/checkout/", {"address_id": self.address.id, "method": method}).json()
                self.assertNotEqual(r["payment_status"], "paid")

    def test_profile_cannot_take_email_of_another_user(self):
        """BUG: registration blocks a taken email in any case, but the profile accepts DANA@example.com."""
        self.login()
        r = self.client.patch("/api/me/", {"email": "DANA@example.com"}, format="json")
        self.assertEqual(r.status_code, 400)

    def test_username_cannot_contain_spaces(self):
        """BUG: the username 'new user' is accepted, the Django admin would refuse it."""
        r = self.post("/api/auth/register/", {"username": "new user", "email": "nu@example.com",
                                              "password": "Shop2026!"})
        self.assertEqual(r.status_code, 400)

    def test_login_is_limited_after_many_wrong_passwords(self):
        """BUG: no protection from password guessing: 15 wrong tries in a row are all answered the same."""
        codes = {APIClient().post("/api/auth/login/", {"username": "aigerim", "password": "wrong"},
                                  format="json").status_code for _ in range(15)}
        self.assertIn(429, codes)