"""Telegram recovery requires an owned binding and a short-lived, one-use code."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import re
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

from django.db import close_old_connections
from django.test import TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from .models import TelegramAccount, TelegramChallenge, User
from .telegram_client import TelegramUnavailable
from .telegram_recovery import process_update


STATUS_URL = "/api/me/telegram/"
LINK_URL = "/api/me/telegram/link/"
UNLINK_URL = "/api/me/telegram/unlink/"
RESET_URL = "/api/auth/telegram/password-reset/"
CONFIRM_URL = "/api/auth/telegram/password-reset/confirm/"
BOT_SETTINGS = {
    "TELEGRAM_BOT_TOKEN": "123456789:ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghi",
    "TELEGRAM_BOT_USERNAME": "sauda_test_bot",
    "PASSWORD_RESET_IP_LIMIT": 1000,
    "PASSWORD_RESET_EMAIL_LIMIT": 1000,
    "PASSWORD_RESET_CONFIRM_LIMIT": 1000,
}
BOT_IDENTITY = {"id": 123456789, "is_bot": True, "username": "sauda_test_bot"}


@override_settings(**BOT_SETTINGS)
class TelegramRecoveryTests(TestCase):
    password = "OriginalTelegram2026!"
    new_password = "RestoredTelegram2027!"
    telegram_id = 123450001

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("telegram_buyer", "telegram-buyer@example.test", cls.password)
        cls.other = User.objects.create_user("telegram_other", "telegram-other@example.test", cls.password)

    def setUp(self):
        self.api = APIClient()
        self.send = patch("shop.telegram_recovery.telegram_client.send_message").start()
        self.addCleanup(patch.stopall)
        self.get_me = patch("shop.telegram_recovery.telegram_client.get_me", return_value=BOT_IDENTITY).start()

    def authenticate(self, user=None):
        self.api.force_authenticate(user or self.user)

    def link_request(self, password=None):
        return self.api.post(LINK_URL, {"current_password": self.password if password is None else password}, format="json")

    def link_nonce(self, response):
        self.assertEqual(response.status_code, 200)
        data = response.json()
        link = urlsplit(data["link_url"])
        self.assertEqual((link.scheme, link.netloc, link.path), ("https", "t.me", "/sauda_test_bot"))
        start = parse_qs(link.query)["start"][0]
        self.assertTrue(start.startswith("link_"))
        nonce = start.removeprefix("link_")
        self.assertGreaterEqual(len(nonce), 32)
        self.assertNotIn(self.password, response.content.decode())
        self.assertGreater(data["expires_in"], 0)
        return nonce

    def bot_start(self, nonce, *, telegram_id=None, chat_id=None, chat_type="private", is_bot=False):
        sender = self.telegram_id if telegram_id is None else telegram_id
        process_update({
            "update_id": 100,
            "message": {
                "message_id": 10,
                "chat": {"id": sender if chat_id is None else chat_id, "type": chat_type},
                "from": {"id": sender, "is_bot": is_bot, "username": "telegram_owner"},
                "text": f"/start link_{nonce}",
            },
        })

    def bind(self, user=None, telegram_id=None):
        return TelegramAccount.objects.create(
            user=user or self.user,
            telegram_id=self.telegram_id if telegram_id is None else telegram_id,
            username="telegram_owner",
        )

    def request_reset(self, identifier=None, **headers):
        return self.api.post(RESET_URL, {
            "identifier": self.user.username if identifier is None else identifier,
        }, format="json", **headers)

    def reset_proof(self):
        response = self.request_reset()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertEqual(set(response.json()), {"challenge_id", "expires_in", "detail"})
        self.assertGreaterEqual(len(response.json()["challenge_id"]), 32)
        args, kwargs = self.send.call_args
        self.assertEqual(args[0] if args else kwargs["chat_id"], self.telegram_id)
        text = args[1] if len(args) > 1 else kwargs["text"]
        codes = re.findall(r"(?<!\d)\d{6}(?!\d)", text)
        self.assertEqual(len(codes), 1)
        return {"challenge_id": response.json()["challenge_id"], "code": codes[0]}

    def confirm(self, proof, **overrides):
        return self.api.post(CONFIRM_URL, {
            **proof, "new_password": self.new_password, "new_password_confirm": self.new_password,
            **overrides,
        }, format="json")

    def assert_invalid_code(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_telegram_code")

    def test_link_and_unlink_endpoints_require_login(self):
        self.assertEqual(self.api.get(STATUS_URL).status_code, 401)
        self.assertEqual(self.link_request().status_code, 401)
        self.assertEqual(self.api.post(UNLINK_URL, {"current_password": self.password}, format="json").status_code, 401)
        self.assertFalse(TelegramAccount.objects.exists())

    def test_link_requires_current_password_and_bot_confirmation(self):
        self.authenticate()
        wrong = self.link_request("wrong-current-password")
        self.assertEqual(wrong.status_code, 400)
        self.assertIn("current_password", wrong.json())
        self.assertFalse(TelegramChallenge.objects.exists())

        nonce = self.link_nonce(self.link_request())
        self.assertFalse(TelegramAccount.objects.exists())
        self.assertFalse(self.api.get(STATUS_URL).json()["linked"])
        self.assertFalse(TelegramChallenge.objects.filter(pk=nonce).exists())
        self.bot_start(nonce)
        account = TelegramAccount.objects.get(user=self.user)
        self.assertEqual(account.telegram_id, self.telegram_id)
        self.assertEqual(account.username, "telegram_owner")
        status = self.api.get(STATUS_URL)
        self.assertEqual(status.status_code, 200)
        self.assertEqual(set(status.json()), {"configured", "linked", "username", "linked_at"})
        self.assertTrue(status.json()["linked"])
        self.assertTrue(status.json()["configured"])
        self.assertNotIn(str(self.telegram_id), status.content.decode())

    def test_link_nonce_is_one_use_and_existing_binding_cannot_be_overwritten(self):
        self.authenticate()
        nonce = self.link_nonce(self.link_request())
        self.bot_start(nonce)
        self.bot_start(nonce, telegram_id=self.telegram_id + 1)
        self.assertEqual(TelegramAccount.objects.get(user=self.user).telegram_id, self.telegram_id)
        self.assertEqual(TelegramAccount.objects.count(), 1)
        response = self.link_request()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["code"], "telegram_already_linked")

    def test_failed_bot_acknowledgement_preserves_committed_binding_and_consumed_nonce(self):
        self.authenticate()
        nonce = self.link_nonce(self.link_request())
        self.send.side_effect = TelegramUnavailable("sensitive-upstream-error")
        with self.assertLogs("shop.telegram_recovery", level="WARNING") as captured:
            self.bot_start(nonce)
        self.assertEqual(TelegramAccount.objects.get(user=self.user).telegram_id, self.telegram_id)
        self.assertTrue(self.api.get(STATUS_URL).json()["linked"])
        challenge = TelegramChallenge.objects.get(user=self.user, purpose="link")
        self.assertIsNotNone(challenge.consumed_at)
        self.assertEqual(self.send.call_count, 1)
        self.assertEqual(len(captured.output), 1)
        self.assertNotIn("sensitive-upstream-error", captured.output[0])

    def test_only_private_matching_human_sender_can_finish_link(self):
        self.authenticate()
        nonce = self.link_nonce(self.link_request())
        for options in (
            {"chat_type": "group"}, {"chat_type": "supergroup"},
            {"chat_id": self.telegram_id + 1}, {"is_bot": True},
            {"telegram_id": True}, {"telegram_id": -1}, {"telegram_id": str(self.telegram_id)},
        ):
            with self.subTest(options=options):
                self.bot_start(nonce, **options)
                self.assertFalse(TelegramAccount.objects.exists())
        self.bot_start(nonce)
        self.assertEqual(TelegramAccount.objects.get().telegram_id, self.telegram_id)

    def test_one_telegram_account_cannot_be_linked_to_two_shop_accounts(self):
        self.bind()
        self.authenticate(self.other)
        nonce = self.link_nonce(self.link_request())
        self.bot_start(nonce)
        self.assertEqual(TelegramAccount.objects.count(), 1)
        self.assertEqual(TelegramAccount.objects.get().user_id, self.user.pk)
        self.assertFalse(TelegramAccount.objects.filter(user=self.other).exists())

    def test_expired_link_and_password_change_invalidate_pending_link(self):
        self.authenticate()
        nonce = self.link_nonce(self.link_request())
        TelegramChallenge.objects.filter(user=self.user, purpose="link").update(expires_at=timezone.now() - timedelta(seconds=1))
        self.bot_start(nonce)
        self.assertFalse(TelegramAccount.objects.exists())
        nonce = self.link_nonce(self.link_request())
        self.user.set_password(self.new_password)
        self.user.save(update_fields=["password"])
        self.bot_start(nonce)
        self.assertFalse(TelegramAccount.objects.exists())

    def test_unlink_requires_password_and_invalidates_existing_recovery(self):
        self.bind()
        proof = self.reset_proof()
        self.authenticate()
        wrong = self.api.post(UNLINK_URL, {"current_password": "wrong"}, format="json")
        self.assertEqual(wrong.status_code, 400)
        self.assertTrue(TelegramAccount.objects.filter(user=self.user).exists())
        response = self.api.post(UNLINK_URL, {"current_password": self.password}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertFalse(TelegramAccount.objects.filter(user=self.user).exists())
        self.assertFalse(TelegramChallenge.objects.filter(user=self.user, consumed_at__isnull=True).exists())
        self.assert_invalid_code(self.confirm(proof))

    def test_code_is_sent_only_to_verified_chat_and_not_returned_or_stored_plaintext(self):
        self.bind()
        proof = self.reset_proof()
        challenge = TelegramChallenge.objects.get(user=self.user, purpose="reset", consumed_at__isnull=True)
        self.assertNotEqual(challenge.key, proof["challenge_id"])
        self.assertNotEqual(challenge.code_digest, proof["code"])
        self.assertTrue(challenge.code_digest)
        self.assertNotIn(proof["code"], vars(challenge).values())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_username_and_email_use_same_bound_chat(self):
        self.bind()
        for identifier in (self.user.username.upper(), self.user.email.upper()):
            with self.subTest(identifier=identifier):
                response = self.request_reset(identifier)
                self.assertEqual(response.status_code, 200)
                args, kwargs = self.send.call_args
                self.assertEqual(args[0] if args else kwargs["chat_id"], self.telegram_id)
        self.assertEqual(self.send.call_count, 2)

    def test_unknown_unlinked_inactive_and_unusable_accounts_have_same_public_response(self):
        self.bind()
        known = self.request_reset().json()
        self.send.reset_mock()
        self.user.is_active = False
        self.user.save(update_fields=["is_active"])
        self.other.set_unusable_password()
        self.other.save(update_fields=["password"])
        self.bind(self.other, telegram_id=self.telegram_id + 1)
        unlinked = User.objects.create_user("unlinked", "unlinked@example.test", self.password)
        for identifier in ("unknown-user", unlinked.username, self.user.username, self.other.username):
            with self.subTest(identifier=identifier):
                response = self.request_reset(identifier)
                self.assertEqual(response.status_code, 200)
                data = response.json()
                self.assertEqual(set(data), set(known))
                self.assertEqual(data["detail"], known["detail"])
                self.assertEqual(data["expires_in"], known["expires_in"])
                self.assertNotEqual(data["challenge_id"], known["challenge_id"])
        self.send.assert_not_called()

    def test_successful_reset_hashes_password_revokes_old_tokens_and_consumes_code(self):
        self.bind()
        tokens = RefreshToken.for_user(self.user)
        proof = self.reset_proof()
        response = self.confirm(proof)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Cache-Control"], "no-store")
        self.assertNotIn("access", response.json())
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.new_password))
        self.assertFalse(self.user.check_password(self.password))
        self.assertNotEqual(self.user.password, self.new_password)
        self.other.refresh_from_db()
        self.assertTrue(self.other.check_password(self.password))
        self.assert_invalid_code(self.confirm(proof))
        self.api.credentials(HTTP_AUTHORIZATION=f"Bearer {tokens.access_token}")
        self.assertEqual(self.api.get("/api/me/").status_code, 401)
        self.assertEqual(self.api.post("/api/auth/refresh/", {"refresh": str(tokens)}, format="json").status_code, 401)

    def test_wrong_codes_are_limited_to_five_attempts(self):
        self.bind()
        proof = self.reset_proof()
        wrong = "000000" if proof["code"] != "000000" else "111111"
        for _ in range(5):
            self.assert_invalid_code(self.confirm({**proof, "code": wrong}))
        self.assert_invalid_code(self.confirm(proof))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_expiry_password_change_and_changed_binding_invalidate_code(self):
        self.bind()
        proof = self.reset_proof()
        TelegramChallenge.objects.filter(user=self.user, purpose="reset").update(expires_at=timezone.now() - timedelta(seconds=1))
        self.assert_invalid_code(self.confirm(proof))
        proof = self.reset_proof()
        self.user.set_password(self.new_password)
        self.user.save(update_fields=["password"])
        self.assert_invalid_code(self.confirm(proof))
        proof = self.reset_proof()
        TelegramAccount.objects.filter(user=self.user).update(telegram_id=self.telegram_id + 1)
        self.assert_invalid_code(self.confirm(proof))

    def test_requesting_new_code_invalidates_previous_challenge(self):
        self.bind()
        first = self.reset_proof()
        second = self.reset_proof()
        self.assert_invalid_code(self.confirm(first))
        self.assertEqual(self.confirm(second).status_code, 200)

    def test_invalid_new_password_preserves_valid_recovery_code(self):
        self.bind()
        proof = self.reset_proof()
        for values, field in (
            ({"new_password_confirm": "DifferentStrong2027!"}, "new_password_confirm"),
            ({"new_password": "weak", "new_password_confirm": "weak"}, "new_password"),
            ({"new_password": self.password, "new_password_confirm": self.password}, "new_password"),
        ):
            with self.subTest(field=field):
                response = self.confirm(proof, **values)
                self.assertEqual(response.status_code, 400)
                self.assertIn(field, response.json())
                self.user.refresh_from_db()
                self.assertTrue(self.user.check_password(self.password))
        self.assertEqual(self.confirm(proof).status_code, 200)

    def test_dummy_unknown_challenge_and_random_proof_cannot_reset_any_account(self):
        self.bind()
        dummy = self.request_reset("unknown-user").json()["challenge_id"]
        for challenge_id in (dummy, "a" * 43):
            self.assert_invalid_code(self.confirm({"challenge_id": challenge_id, "code": "123456"}))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))

    def test_public_recovery_ignores_expired_authorization(self):
        self.bind()
        self.api.credentials(HTTP_AUTHORIZATION="Bearer invalid-or-expired")
        proof = self.reset_proof()
        self.assertEqual(self.confirm(proof).status_code, 200)

    def test_malformed_recovery_payloads_return_validation_errors_without_mutation(self):
        for payload in ({}, {"identifier": ""}, {"identifier": []}, {"identifier": "a" * 1000}, [], None):
            with self.subTest(payload=payload):
                self.assertEqual(self.api.post(RESET_URL, payload, format="json").status_code, 400)
        for payload in ({}, {"challenge_id": [], "code": "123456"}, [], None):
            with self.subTest(payload=payload):
                self.assertEqual(self.api.post(CONFIRM_URL, payload, format="json").status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password(self.password))
        self.send.assert_not_called()

    @override_settings(TELEGRAM_BOT_TOKEN="")
    def test_missing_bot_configuration_is_not_reported_as_delivery(self):
        self.bind()
        for identifier in (self.user.username, "unknown-user"):
            response = self.request_reset(identifier)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], "telegram_not_configured")
        self.send.assert_not_called()

    def test_global_bot_failure_is_identical_for_known_and_unknown_accounts(self):
        self.bind()
        self.get_me.side_effect = TelegramUnavailable("Telegram is unavailable")
        responses = [self.request_reset(identifier) for identifier in (self.user.username, "unknown-user")]
        self.assertEqual([response.status_code for response in responses], [503, 503])
        self.assertEqual(responses[0].json(), responses[1].json())
        self.assertEqual(responses[0].json()["code"], "telegram_unavailable")
        self.send.assert_not_called()

    def test_wrong_bot_identity_is_rejected_before_any_code_delivery(self):
        self.bind()
        self.get_me.return_value = {**BOT_IDENTITY, "username": "another_bot"}
        response = self.request_reset()
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["code"], "telegram_unavailable")
        self.send.assert_not_called()

    def test_recipient_specific_delivery_failure_keeps_generic_response_and_unusable_code(self):
        self.bind()
        self.send.side_effect = TelegramUnavailable("Recipient is unavailable")
        known = self.request_reset()
        unknown = self.request_reset("unknown-user")
        self.assertEqual(known.status_code, 200)
        self.assertEqual(unknown.status_code, 200)
        self.assertEqual(known.json()["detail"], unknown.json()["detail"])
        self.assert_invalid_code(self.confirm({"challenge_id": known.json()["challenge_id"], "code": "123456"}))

    @override_settings(PASSWORD_RESET_EMAIL_LIMIT=2)
    def test_request_limit_is_case_insensitive_and_shared_between_sources(self):
        self.bind()
        self.assertEqual(self.request_reset().status_code, 200)
        self.assertEqual(self.request_reset(self.user.username.upper(), REMOTE_ADDR="192.0.2.20").status_code, 200)
        response = self.request_reset(REMOTE_ADDR="192.0.2.21")
        self.assertEqual(response.status_code, 429)
        self.assertGreater(int(response["Retry-After"]), 0)
        self.assertEqual(self.send.call_count, 2)


@override_settings(**BOT_SETTINGS)
class ConcurrentTelegramRecoveryTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_only_one_concurrent_request_can_use_a_recovery_code(self):
        user = User.objects.create_user("telegram_concurrent", "telegram-concurrent@example.test", "OriginalTelegram2026!")
        TelegramAccount.objects.create(user=user, telegram_id=123450002, username="concurrent_owner")
        with patch("shop.telegram_recovery.telegram_client.get_me", return_value=BOT_IDENTITY), patch("shop.telegram_recovery.telegram_client.send_message") as send:
            response = APIClient().post(RESET_URL, {"identifier": user.username}, format="json")
        self.assertEqual(response.status_code, 200)
        args, kwargs = send.call_args
        text = args[1] if len(args) > 1 else kwargs["text"]
        code = re.search(r"(?<!\d)\d{6}(?!\d)", text).group()
        payload = {
            "challenge_id": response.json()["challenge_id"], "code": code,
            "new_password": "SaffronOrbit2027!", "new_password_confirm": "SaffronOrbit2027!",
        }
        barrier = Barrier(2)

        def submit(index):
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return APIClient().post(CONFIRM_URL, payload, format="json", REMOTE_ADDR=f"192.0.2.{index}").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit, (1, 2))), [200, 400])
