"""Recovery only grants access to the holder of a valid, single-use email link."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import re
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone
from django.utils.http import urlsafe_base64_encode
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import LoginSecurityState, User


REQUEST_URL = "/api/auth/password-reset/"
CONFIRM_URL = "/api/auth/password-reset/confirm/"


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend", FRONTEND_URL="http://localhost:4200")
class PasswordResetTests(TestCase):
    password = "OriginalStrong2026!"
    new_password = "RestoredStrong2027!"

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("recover", "recover@example.test", cls.password)
        cls.other = User.objects.create_user("another", "another@example.test", cls.password)

    def setUp(self):
        self.api = APIClient()

    def request_reset(self, email=None, **headers):
        return self.api.post(REQUEST_URL, {"email": email or self.user.email}, format="json", **headers)

    def proof(self, user=None):
        user = user or self.user
        return {"uid": urlsafe_base64_encode(str(user.pk).encode()), "token": default_token_generator.make_token(user)}

    def confirm(self, proof=None, **overrides):
        return self.api.post(CONFIRM_URL, {
            **(self.proof() if proof is None else proof),
            "new_password": self.new_password,
            "new_password_confirm": self.new_password,
            **overrides,
        }, format="json")

    @override_settings(ALLOWED_HOSTS=["testserver", "attacker.example"])
    def test_request_emails_frontend_link_without_changing_password_or_exposing_proof(self):
        response = self.request_reset("RECOVER@EXAMPLE.TEST", HTTP_HOST="attacker.example", HTTP_ORIGIN="https://attacker.example")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(set(response.json()), {"detail"})
        self.assertEqual(len(mail.outbox), 1)
        message = mail.outbox[0]
        self.assertEqual(message.to, [self.user.email])
        link = re.search(r"http://localhost:4200/reset-password\?\S+", message.body).group()
        proof = {key: value[0] for key, value in parse_qs(urlsplit(link).query).items()}
        self.assertEqual(proof["uid"], self.proof()["uid"])
        self.assertTrue(default_token_generator.check_token(self.user, proof["token"]))
        self.assertNotIn("attacker.example", message.body)
        self.assertNotIn(proof["token"], response.content.decode())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.confirm(proof).status_code, 200)

    def test_unknown_inactive_and_unusable_accounts_have_same_response_without_email(self):
        expected = self.request_reset().json()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.other.set_unusable_password()
        self.other.save(update_fields=["password"])
        mail.outbox.clear()
        for email in ("missing@example.test", self.user.email, self.other.email):
            response = self.request_reset(email)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), expected)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_email_and_non_object_payloads_are_rejected(self):
        for payload in ({}, {"email": "wrong"}, {"email": "a" * 300 + "@example.test"}, [], None):
            with self.subTest(payload=payload):
                self.assertEqual(self.api.post(REQUEST_URL, payload, format="json").status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_reset_hashes_password_revokes_old_tokens_and_consumes_all_reset_links(self):
        old_tokens = RefreshToken.for_user(self.user)
        proof = self.proof()
        response = self.confirm(proof)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("access", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertNotEqual(self.user.password, self.new_password)
        self.assertFalse(self.user.check_password(self.password))
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password(self.password))
        self.assertEqual(self.confirm(proof).json()["code"], "invalid_reset_link")
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {old_tokens.access_token}")
        self.assertEqual(self.api.get("/api/me/").status_code, 401)
        self.assertEqual(self.api.post("/api/auth/refresh/", {"refresh": str(old_tokens)}, format="json").status_code, 401)
        self.api.credentials()
        self.assertEqual(self.api.post("/api/auth/login/", {
            "username": self.user.username, "password": self.new_password,
        }, format="json").status_code, 200)

    def test_invalid_expired_wrong_user_and_malformed_links_cannot_change_password(self):
        proof = self.proof()
        cases = (
            {**proof, "token": proof["token"] + "x"},
            {**proof, "uid": self.proof(self.other)["uid"]},
            {**proof, "uid": "invalid"},
            {**proof, "uid": urlsafe_base64_encode(b"999999999999999999999999999999")},
            {**proof, "uid": urlsafe_base64_encode(b"-1")},
            {**proof, "uid": urlsafe_base64_encode(b"\xff")},
        )
        for item in cases:
            with self.subTest(item=item):
                response = self.confirm(item)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.json()["code"], "invalid_reset_link")
        started = datetime(2026, 11, 20, 12)
        with patch.object(default_token_generator, "_now", return_value=started):
            expired = self.proof()
        with patch.object(default_token_generator, "_now", return_value=started + timedelta(seconds=3601)):
            self.assertEqual(self.confirm(expired).json()["code"], "invalid_reset_link")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_validation_failure_preserves_link_and_password(self):
        proof = self.proof()
        cases = (
            ({"new_password_confirm": "MismatchStrong2027!"}, "new_password_confirm"),
            ({"new_password": "weak", "new_password_confirm": "weak"}, "new_password"),
            ({"new_password": self.password, "new_password_confirm": self.password}, "new_password"),
        )
        for payload, field in cases:
            response = self.confirm(proof, **payload)
            self.assertEqual(response.status_code, 400)
            self.assertIn(field, response.json())
            self.user.refresh_from_db()
            self.assertTrue(self.user.check_password(self.password))
            self.assertTrue(default_token_generator.check_token(self.user, proof["token"]))
        self.assertEqual(self.confirm(proof).status_code, 200)

    def test_password_or_email_change_and_deactivation_invalidate_link(self):
        proof = self.proof()
        self.user.email = "changed@example.test"
        self.user.save(update_fields=["email"])
        self.assertEqual(self.confirm(proof).json()["code"], "invalid_reset_link")
        proof = self.proof()
        self.user.set_password("ChangedStrong2028!")
        self.user.save(update_fields=["password"])
        self.assertEqual(self.confirm(proof).json()["code"], "invalid_reset_link")
        proof = self.proof()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.assertEqual(self.confirm(proof).json()["code"], "invalid_reset_link")

    def test_public_recovery_ignores_stale_authorization(self):
        self.api.credentials(HTTP_AUTHORIZATION="Bearer expired-or-invalid")
        self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(self.confirm().status_code, 200)

    @override_settings(PASSWORD_RESET_EMAIL_LIMIT=2)
    def test_email_limit_is_case_insensitive_and_shared_across_sources(self):
        self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(self.request_reset(self.user.email.upper(), REMOTE_ADDR="192.0.2.10").status_code, 200)
        response = self.request_reset(REMOTE_ADDR="192.0.2.11")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(len(mail.outbox), 2)
        # These counters must not lock out ordinary account sign-in.
        self.assertFalse(LoginSecurityState.objects.filter(scope__startswith="login_").exists())

    @override_settings(PASSWORD_RESET_IP_LIMIT=2)
    def test_source_limit_counts_unknown_emails_and_ignores_forwarded_ip(self):
        self.request_reset("one@example.test")
        self.request_reset("two@example.test")
        before = LoginSecurityState.objects.count()
        response = self.request_reset("three@example.test", HTTP_X_FORWARDED_FOR="192.0.2.50")
        self.assertEqual(response.status_code, 429)
        self.assertEqual(LoginSecurityState.objects.count(), before)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(PASSWORD_RESET_CONFIRM_LIMIT=2)
    def test_confirm_limit_expires_without_extending_window(self):
        started = timezone.now()
        with patch("shop.password_reset.timezone.now", return_value=started):
            self.confirm({"uid": "bad", "token": "bad"})
            self.confirm({"uid": "bad", "token": "bad"})
        with patch("shop.password_reset.timezone.now", return_value=started + timedelta(seconds=100)):
            response = self.confirm()
            self.assertEqual(response.status_code, 429)
            self.assertEqual(int(response["Retry-After"]), 800)
        with patch("shop.password_reset.timezone.now", return_value=started + timedelta(seconds=901)):
            self.assertEqual(self.confirm().status_code, 200)


class ConcurrentPasswordResetTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_only_one_concurrent_request_can_use_a_link(self):
        user = User.objects.create_user("concurrent", "concurrent@example.test", "OriginalStrong2026!")
        proof = {
            "uid": urlsafe_base64_encode(str(user.pk).encode()),
            "token": default_token_generator.make_token(user),
            "new_password": "ConcurrentStrong2027!",
            "new_password_confirm": "ConcurrentStrong2027!",
        }
        barrier = Barrier(2)

        def submit(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return APIClient().post(CONFIRM_URL, proof, format="json", REMOTE_ADDR=f"192.0.2.{index}").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit, (1, 2))), [200, 400])
