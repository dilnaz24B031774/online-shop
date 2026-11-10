"""Exercise both real login endpoints, including their shared lockout state."""
from datetime import timedelta
from unittest.mock import patch

from django.test import RequestFactory, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .auth_forms import ProtectedAdminAuthenticationForm
from .login_security import get_login_state
from .models import LoginChallenge, LoginSecurityState, User


class ProtectedLoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.password = "LoginStrong2026!"
        cls.user = User.objects.create_superuser(
            "operator", "operator@test.example", cls.password, role=User.Role.ADMIN,
        )

    def setUp(self):
        self.api = APIClient()
        self.request = RequestFactory().post("/api/auth/login/", REMOTE_ADDR="127.0.0.1")

    def login(self, password=None, **proof):
        return self.api.post("/api/auth/login/", {
            "username": self.user.username, "password": self.password if password is None else password,
            **proof,
        }, format="json")

    def fail(self, count):
        response = None
        for _ in range(count):
            response = self.login(password="wrong")
        return response

    def proof(self):
        response = self.api.get("/api/auth/challenge/")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        left, _, right, *_ = data["prompt"].split()
        return {"challenge_id": data["id"], "challenge_answer": str(int(left) + int(right))}

    def test_success_issues_tokens_and_resets_previous_pair_failures(self):
        self.assertEqual(self.fail(2).status_code, 401)
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertIn("access", response.json())
        self.assertIn("refresh", response.json())
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(get_login_state(self.request, "operator")["remaining_attempts"], 5)

    def test_correct_password_requires_challenge_after_three_errors(self):
        response = self.fail(3)
        self.assertTrue(response.json()["challenge_required"])
        response = self.login()
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "challenge_required")
        self.assertNotIn("access", response.json())
        response = self.login(**self.proof())
        self.assertEqual(response.status_code, 200)
        self.assertFalse(LoginChallenge.objects.exists())

    def test_fifth_rejection_blocks_correct_password_for_five_minutes(self):
        response = self.fail(5)
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.json()["code"], "login_locked")
        self.assertGreaterEqual(int(response["Retry-After"]), 299)
        deadline = LoginSecurityState.objects.get(scope="login_pair").locked_until
        response = self.login()
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("access", response.json())
        self.assertEqual(LoginSecurityState.objects.get(scope="login_pair").locked_until, deadline)

    def test_lock_expires_and_allows_login_again(self):
        started = timezone.now()
        with patch("shop.login_security.timezone.now", return_value=started):
            self.fail(5)
        with patch("shop.login_security.timezone.now", return_value=started + timedelta(seconds=301)):
            self.assertEqual(self.login().status_code, 200)

    def test_honeypot_rejects_even_the_right_password(self):
        response = self.login(website="https://bot.example")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["remaining_attempts"], 4)
        self.assertNotIn("access", response.json())

    def test_admin_failures_also_lock_the_api(self):
        for _ in range(5):
            response = self.client.post("/admin/login/", {"username": "operator", "password": "wrong"})
            self.assertEqual(response.status_code, 200)
        self.assertContains(response, "login-countdown")
        self.assertEqual(self.login().status_code, 429)
        response = self.client.post("/admin/login/", {"username": "operator", "password": self.password})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_api_challenge_requirement_cannot_be_bypassed_via_admin(self):
        self.fail(3)
        response = self.client.post("/admin/login/", {"username": "operator", "password": self.password})
        self.assertContains(response, "Проверка перед входом")
        self.assertNotIn("_auth_user_id", self.client.session)
        challenge = response.context["form"].bot_challenge
        left, _, right, *_ = challenge["prompt"].split()
        response = self.client.post("/admin/login/", {
            "username": "operator", "password": self.password, "next": "/staff/",
            "challenge_id": challenge["id"], "challenge_answer": str(int(left) + int(right)),
        })
        self.assertRedirects(response, "/staff/")
        self.assertEqual(self.client.session["_auth_user_id"], str(self.user.pk))

    def test_unknown_and_existing_accounts_get_the_same_rejection(self):
        known = self.login(password="wrong")
        unknown = self.api.post("/api/auth/login/", {"username": "unknown", "password": "wrong"}, format="json")
        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.json(), unknown.json())

    def test_public_auth_endpoints_ignore_stale_bearer_tokens(self):
        self.api.credentials(HTTP_AUTHORIZATION="Bearer invalid-expired-token")
        self.assertEqual(self.api.get("/api/auth/challenge/").status_code, 200)
        self.assertEqual(self.login().status_code, 200)

    def test_malformed_json_and_fields_are_rejected_without_server_error(self):
        cases = [[], ["username"], "text", {"username": [], "password": {}},
                 {"username": "x" * 151, "password": "x"}, {"username": "operator", "password": "x" * 4097}]
        for index, payload in enumerate(cases):
            with self.subTest(payload_type=type(payload).__name__):
                response = self.api.post("/api/auth/login/", payload, format="json", REMOTE_ADDR=f"192.0.2.{index + 1}")
                self.assertEqual(response.status_code, 401)
                self.assertNotIn("access", response.json())

    def test_challenge_endpoint_is_no_store_and_rate_limited(self):
        response = self.api.get("/api/auth/challenge/")
        self.assertEqual(response["Cache-Control"], "no-store")
        for _ in range(19):
            self.assertEqual(self.api.get("/api/auth/challenge/").status_code, 200)
        response = self.api.get("/api/auth/challenge/")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)

    def test_admin_form_can_be_constructed_without_request(self):
        self.assertEqual(ProtectedAdminAuthenticationForm().retry_after, 0)
