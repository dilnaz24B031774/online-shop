from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from .accounts import normalize_phone, suggest_usernames
from .models import User

PASSWORD = "Shop2026!"


class UsernameRulesTests(TestCase):
    def setUp(self):
        self.api = APIClient()
        User.objects.create_user("aigerim", "aigerim@example.com", PASSWORD, first_name="Aigerim", last_name="Kairatova")

    def register(self, username, email="new@example.com"):
        return self.api.post("/api/auth/register/", {"username": username, "email": email, "password": PASSWORD}, format="json")

    def test_check_endpoint(self):
        r = self.api.get("/api/auth/username-check/", {"username": "AIGERIM"}).json()
        self.assertEqual((r["available"], r["code"]), (False, "taken"))
        self.assertEqual(len(r["suggestions"]), 3)
        self.assertTrue(self.api.get("/api/auth/username-check/", {"username": "nice.name_1"}).json()["available"])

    def test_bad_usernames_rejected_on_register(self):
        for bad in ("ab", "new user", "имя", "_start", "end.", "a..b", "x" * 31, "Admin"):
            self.assertEqual(self.register(bad).status_code, 400, bad)
        self.assertEqual(self.register("Aigerim").status_code, 400)

    def test_good_username_registers(self):
        self.assertEqual(self.register("dana.k-2026").status_code, 201)

    def test_suggestions_are_free(self):
        for name in suggest_usernames("aigerim"):
            self.assertFalse(User.objects.filter(username__iexact=name).exists())

    def test_database_blocks_same_username_in_other_case(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("AIGERIM", "other@example.com", PASSWORD)

    def test_database_blocks_same_email_in_other_case(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.create_user("other", "AIGERIM@example.com", PASSWORD)


class LoginTests(TestCase):
    def setUp(self):
        User.objects.create_user("aigerim", "aigerim@example.com", PASSWORD)

    def login(self, name):
        return APIClient().post("/api/auth/login/", {"username": name, "password": PASSWORD}, format="json")

    def test_login_by_username_any_case_and_by_email(self):
        for name in ("aigerim", "AiGeRiM", "aigerim@example.com", "AIGERIM@EXAMPLE.COM"):
            self.assertEqual(self.login(name).status_code, 200, name)

    def test_wrong_password_still_rejected(self):
        r = APIClient().post("/api/auth/login/", {"username": "aigerim@example.com", "password": "wrong"}, format="json")
        self.assertEqual(r.status_code, 401)


class PhoneAndNumberTests(TestCase):
    def setUp(self):
        self.a = User.objects.create_user("aigerim", "a@example.com", PASSWORD, phone="+77011111111")
        self.b = User.objects.create_user("dana", "d@example.com", PASSWORD)
        self.api = APIClient()
        self.api.force_authenticate(self.b)

    def test_phone_is_normalized(self):
        self.assertEqual(normalize_phone("8 (702) 222-22-22"), "+77022222222")
        self.assertEqual(normalize_phone("702 222 22 22"), "+77022222222")
        r = self.api.patch("/api/me/", {"phone": "8 702 222 22 22"}, format="json")
        self.assertEqual(r.json()["phone"], "+77022222222")

    def test_same_phone_in_two_accounts_rejected(self):
        r = self.api.patch("/api/me/", {"phone": "8 701 111 11 11"}, format="json")
        self.assertEqual(r.status_code, 400)
        with self.assertRaises(IntegrityError), transaction.atomic():
            User.objects.filter(pk=self.b.pk).update(phone="+77011111111")

    def test_customer_number_and_review_author(self):
        me = self.api.get("/api/me/").json()
        self.assertEqual(me["customer_number"], 100000 + self.b.pk)
        from .accounts import display_name
        self.a.first_name, self.a.last_name = "Aigerim", "Kairatova"
        self.assertEqual(display_name(self.a), "Aigerim K.")
        self.assertEqual(display_name(self.b), "dana")
