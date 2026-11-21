"""Customer settings use the authenticated account and never expose passwords."""
from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import User
from .serializers import UserSerializer


class CustomerSettingsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "OriginalStrong2026!"
        cls.new_password = "UpdatedStrong2027!"
        cls.user = User.objects.create_user(
            "customer", "customer@example.test", cls.password,
            first_name="Aigerim", phone="+77001234567",
        )
        cls.other = User.objects.create_user("another", "another@example.test", cls.password)

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def change_password(self, **overrides):
        return self.api.post("/api/me/password/", {
            "current_password": self.password,
            "new_password": self.new_password,
            "new_password_confirm": self.new_password,
            **overrides,
        }, format="json")

    def test_profile_update_persists_and_is_visible_after_reload(self):
        response = self.api.patch("/api/me/", {
            "username": "updated_customer", "first_name": "Айгерім", "last_name": "Кайратова",
            "phone": "+7 (701) 234-56-78", "preferred_currency": "KZT",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["phone"], "+77012345678")
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "updated_customer")
        self.assertEqual(self.user.first_name, "Айгерім")
        self.assertEqual(self.user.last_name, "Кайратова")
        self.assertEqual(self.user.preferred_currency, "KZT")
        response = self.api.get("/api/me/")
        self.assertEqual(response.json()["preferred_currency"], "KZT")
        self.assertNotIn("password", response.json())
        public = APIClient()
        self.assertEqual(public.post("/api/auth/login/", {
            "username": "updated_customer", "password": self.password,
        }, format="json").status_code, 200)

    def test_default_currency_and_all_supported_preferences(self):
        self.assertEqual(self.api.get("/api/me/").json()["preferred_currency"], "USD")
        for currency in ("KZT", "EUR", "RUB", "USD"):
            with self.subTest(currency=currency):
                response = self.api.patch("/api/me/", {"preferred_currency": currency}, format="json")
                self.assertEqual(response.status_code, 200)
                self.user.refresh_from_db()
                self.assertEqual(self.user.preferred_currency, currency)

    def test_currency_and_phone_validation_does_not_partially_save(self):
        for payload, field in (
            ({"preferred_currency": "BTC"}, "preferred_currency"),
            ({"phone": "call me tomorrow"}, "phone"),
            ({"phone": "+123"}, "phone"),
            ({"phone": "+1234567890123456"}, "phone"),
            ({"phone": "++77001234567"}, "phone"),
            ({"first_name": "a" * 151}, "first_name"),
            ({"first_name": "Name\x00Here"}, "first_name"),
        ):
            with self.subTest(payload=payload):
                response = self.api.patch("/api/me/", {"last_name": "Should not save", **payload}, format="json")
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
                self.user.refresh_from_db()
                self.assertEqual(self.user.last_name, "")

    def test_phone_can_be_cleared(self):
        response = self.api.patch("/api/me/", {"phone": ""}, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.assertEqual(self.user.phone, "")

    def test_username_uniqueness_is_case_insensitive(self):
        for username in ("another", "ANOTHER"):
            response = self.api.patch("/api/me/", {"username": username}, format="json")
            self.assertEqual(response.status_code, 400)
            self.assertIn("username", response.json())
        # Saving the current username is allowed.
        self.assertEqual(self.api.patch("/api/me/", {"username": "customer"}, format="json").status_code, 200)

    def test_settings_cannot_change_another_account_or_grant_staff_access(self):
        response = self.api.patch("/api/me/", {
            "id": self.other.pk, "role": "admin", "is_staff": True,
            "is_superuser": True, "password": "InjectedPassword2026!", "first_name": "Mine",
        }, format="json")
        self.assertEqual(response.status_code, 200)
        self.user.refresh_from_db()
        self.other.refresh_from_db()
        self.assertEqual(self.user.first_name, "Mine")
        self.assertEqual(self.user.role, "customer")
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.other.first_name, "")

    def test_profile_save_cannot_restore_a_stale_password(self):
        stale_user = User.objects.get(pk=self.user.pk)
        changed_user = User.objects.get(pk=self.user.pk)
        changed_user.set_password(self.new_password)
        changed_user.save(update_fields=["password"])
        serializer = UserSerializer(stale_user, data={"first_name": "Updated"}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        serializer.save()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertEqual(self.user.first_name, "Updated")

    def test_anonymous_requests_cannot_access_settings(self):
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get("/api/me/").status_code, 401)
        self.assertEqual(self.api.patch("/api/me/", {"first_name": "Other"}, format="json").status_code, 401)
        self.assertEqual(self.change_password().status_code, 401)

    def test_wrong_current_password_is_rejected_without_mutation(self):
        response = self.change_password(current_password="WrongPassword2026!")
        self.assertEqual(response.status_code, 400)
        self.assertIn("current_password", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_mismatched_weak_and_reused_passwords_are_rejected(self):
        cases = (
            ({"new_password_confirm": "DifferentStrong2028!"}, "new_password_confirm"),
            ({"new_password": "weak", "new_password_confirm": "weak"}, "new_password"),
            ({"new_password": self.password, "new_password_confirm": self.password}, "new_password"),
        )
        for payload, field in cases:
            with self.subTest(field=field):
                response = self.change_password(**payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(self.password))

    def test_password_change_hashes_password_and_replaces_all_old_tokens(self):
        old_refresh = RefreshToken.for_user(self.user)
        old_access = str(old_refresh.access_token)
        # Exercise actual JWT authentication instead of force_authenticate.
        self.api.force_authenticate(None)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {old_access}")
        response = self.change_password()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        tokens = response.json()
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.password))
        self.assertNotEqual(self.user.password, self.new_password)
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password(self.password))

        self.assertEqual(self.api.get("/api/me/").status_code, 401)
        public = APIClient()
        self.assertEqual(public.post("/api/auth/refresh/", {"refresh": str(old_refresh)}, format="json").status_code, 401)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens['access']}")
        self.assertEqual(self.api.get("/api/me/").status_code, 200)
        refreshed = public.post("/api/auth/refresh/", {"refresh": tokens["refresh"]}, format="json")
        self.assertEqual(refreshed.status_code, 200)
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {refreshed.json()['access']}")
        self.assertEqual(self.api.get("/api/me/").status_code, 200)
        self.assertEqual(public.post("/api/auth/login/", {
            "username": self.user.username, "password": self.password,
        }, format="json").status_code, 401)
        self.assertEqual(public.post("/api/auth/login/", {
            "username": self.user.username, "password": self.new_password,
        }, format="json").status_code, 200)

