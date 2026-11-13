"""Persistent lockouts, single-use challenges, and concurrent accounting."""
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch

from django.db import close_old_connections, connection
from django.test import RequestFactory, TestCase, TransactionTestCase, override_settings, skipUnlessDBFeature
from django.utils import timezone

from .login_security import (
    SecurityRateLimited, _cleanup, get_login_state, issue_challenge, login_attempt,
    record_login_failure, record_login_success, verify_challenge,
)
from .models import LoginChallenge, LoginSecurityState


@override_settings(
    LOGIN_MAX_FAILURES=5, LOGIN_LOCKOUT_SECONDS=300, LOGIN_FAILURE_WINDOW_SECONDS=300,
    LOGIN_IP_MAX_FAILURES=20, LOGIN_CHALLENGE_AFTER=3, LOGIN_IP_CHALLENGE_AFTER=10,
    CHALLENGE_MAX_ISSUED_PER_MINUTE=20, LOGIN_CHALLENGE_TTL_SECONDS=120,
)
class LoginSecurityTests(TestCase):
    def setUp(self):
        self.request = RequestFactory().post("/api/auth/login/", REMOTE_ADDR="192.0.2.10")

    def fail(self, username="alice", count=1):
        state = None
        for _ in range(count):
            with login_attempt(self.request, username):
                state = record_login_failure(self.request, username)
        return state

    def answer(self, challenge):
        left, _, right, *_ = challenge["prompt"].split()
        return str(int(left) + int(right))

    def test_initial_status_does_not_allocate_counters(self):
        self.assertEqual(get_login_state(self.request, "alice"), {
            "retry_after": 0, "challenge_required": False, "remaining_attempts": 5,
        })
        self.assertFalse(LoginSecurityState.objects.exists())

    def test_fifth_failure_locks_for_five_minutes(self):
        state = self.fail(count=4)
        self.assertEqual(state["retry_after"], 0)
        self.assertEqual(state["remaining_attempts"], 1)
        state = self.fail()
        self.assertEqual(state["retry_after"], 300)
        self.assertEqual(state["remaining_attempts"], 0)

    def test_challenge_is_requested_after_three_failures(self):
        self.assertFalse(self.fail(count=2)["challenge_required"])
        self.assertTrue(self.fail()["challenge_required"])

    def test_lock_is_not_extended_by_rejected_traffic(self):
        started = timezone.now()
        with patch("shop.login_security.timezone.now", return_value=started):
            self.fail(count=5)
        locked_until = LoginSecurityState.objects.get(scope="login_pair").locked_until
        with patch("shop.login_security.timezone.now", return_value=started + timedelta(seconds=100)):
            state = self.fail(count=4)
        self.assertEqual(state["retry_after"], 200)
        self.assertEqual(LoginSecurityState.objects.get(scope="login_pair").locked_until, locked_until)
        self.assertEqual(LoginSecurityState.objects.get(scope="login_source").attempts, 5)

    def test_lock_expires_without_manual_unblocking(self):
        started = timezone.now()
        with patch("shop.login_security.timezone.now", return_value=started):
            self.fail(count=5)
        with patch("shop.login_security.timezone.now", return_value=started + timedelta(seconds=301)):
            self.assertEqual(get_login_state(self.request, "alice")["remaining_attempts"], 5)
            state = self.fail()
        self.assertEqual(state["retry_after"], 0)
        self.assertEqual(state["remaining_attempts"], 4)

    def test_old_failure_window_resets_even_without_a_lock(self):
        started = timezone.now()
        with patch("shop.login_security.timezone.now", return_value=started):
            self.fail(count=4)
        with patch("shop.login_security.timezone.now", return_value=started + timedelta(seconds=301)):
            self.assertEqual(self.fail()["remaining_attempts"], 4)

    def test_account_spellings_share_a_pair_counter(self):
        self.fail(" Alice ", 3)
        self.fail("ＡＬＩＣＥ", 2)
        self.assertEqual(get_login_state(self.request, "alice")["retry_after"], 300)

    def test_pair_lock_does_not_lock_another_source(self):
        self.fail(count=5)
        other = RequestFactory().post("/api/auth/login/", REMOTE_ADDR="192.0.2.11")
        self.assertEqual(get_login_state(other, "alice")["retry_after"], 0)

    def test_untrusted_forwarding_header_cannot_evade_lock(self):
        self.fail(count=5)
        self.request.META["HTTP_X_FORWARDED_FOR"] = "203.0.113.55"
        self.assertEqual(get_login_state(self.request, "alice")["retry_after"], 300)

    def test_source_limit_stops_password_spraying_across_usernames(self):
        for index in range(20):
            state = self.fail(username=f"buyer-{index}")
        self.assertEqual(state["retry_after"], 300)
        self.assertEqual(get_login_state(self.request, "new-account")["retry_after"], 300)

    def test_source_challenge_threshold_applies_to_new_usernames(self):
        for index in range(10):
            self.fail(username=f"buyer-{index}")
        self.assertTrue(get_login_state(self.request, "different")["challenge_required"])

    def test_blocked_source_cannot_allocate_rows_for_more_random_names(self):
        for index in range(20):
            self.fail(username=f"buyer-{index}")
        count = LoginSecurityState.objects.count()
        for index in range(20):
            state = self.fail(username=f"blocked-random-{index}")
            self.assertGreater(state["retry_after"], 0)
        self.assertEqual(LoginSecurityState.objects.count(), count)

    def test_success_clears_pair_but_retains_source_history(self):
        self.fail(count=3)
        with login_attempt(self.request, "alice"):
            record_login_success(self.request, "alice")
        self.assertFalse(get_login_state(self.request, "alice")["challenge_required"])
        self.assertEqual(LoginSecurityState.objects.get(scope="login_pair").attempts, 0)
        self.assertEqual(LoginSecurityState.objects.get(scope="login_source").attempts, 3)

    def test_even_success_cannot_clear_an_active_lock(self):
        self.fail(count=5)
        with self.assertRaises(SecurityRateLimited):
            record_login_success(self.request, "alice")
        self.assertEqual(get_login_state(self.request, "alice")["retry_after"], 300)

    def test_counter_keys_do_not_store_username_or_address(self):
        self.fail()
        for bucket in LoginSecurityState.objects.all():
            self.assertEqual(len(bucket.key), 64)
            self.assertNotIn("alice", bucket.key)
            self.assertNotIn("192.0.2.10", bucket.key)

    def test_challenge_contains_only_opaque_id_and_prompt_and_is_single_use(self):
        challenge = issue_challenge(self.request)
        self.assertEqual(set(challenge), {"id", "prompt", "expires_in"})
        stored = LoginChallenge.objects.get(pk=challenge["id"])
        self.assertNotEqual(stored.answer_digest, self.answer(challenge))
        self.assertEqual(len(stored.answer_digest), 64)
        self.assertTrue(verify_challenge(self.request, challenge["id"], self.answer(challenge)))
        self.assertFalse(verify_challenge(self.request, challenge["id"], self.answer(challenge)))

    def test_wrong_answer_consumes_challenge(self):
        challenge = issue_challenge(self.request)
        self.assertFalse(verify_challenge(self.request, challenge["id"], "999"))
        self.assertFalse(verify_challenge(self.request, challenge["id"], self.answer(challenge)))

    def test_expired_challenge_is_refused(self):
        started = timezone.now()
        with patch("shop.login_security.timezone.now", return_value=started):
            challenge = issue_challenge(self.request)
        with patch("shop.login_security.timezone.now", return_value=started + timedelta(seconds=121)):
            self.assertFalse(verify_challenge(self.request, challenge["id"], self.answer(challenge)))

    def test_challenge_is_bound_to_source_and_purpose(self):
        other = RequestFactory().post("/api/auth/login/", REMOTE_ADDR="192.0.2.11")
        challenge = issue_challenge(self.request)
        self.assertFalse(verify_challenge(other, challenge["id"], self.answer(challenge)))
        challenge = issue_challenge(self.request, purpose="register")
        self.assertFalse(verify_challenge(self.request, challenge["id"], self.answer(challenge), purpose="login"))

    def test_malformed_challenge_input_is_safe(self):
        for identifier in (None, [], {}, 123, "x" * 100):
            self.assertFalse(verify_challenge(self.request, identifier, {}))
        for answer in (None, [], {}, "9" * 10000, True):
            challenge = issue_challenge(self.request)
            self.assertFalse(verify_challenge(self.request, challenge["id"], answer))

    def test_challenge_issuance_is_rate_limited_and_recovers_after_a_minute(self):
        started = timezone.now()
        with patch("shop.login_security.timezone.now", return_value=started):
            for _ in range(20):
                issue_challenge(self.request)
            with self.assertRaises(SecurityRateLimited) as caught:
                issue_challenge(self.request)
            self.assertEqual(caught.exception.retry_after, 60)
        with patch("shop.login_security.timezone.now", return_value=started + timedelta(seconds=61)):
            self.assertIn("id", issue_challenge(self.request))

    def test_cleanup_removes_expired_records_but_keeps_active_locks(self):
        now = timezone.now()
        challenge = issue_challenge(self.request)
        LoginChallenge.objects.filter(pk=challenge["id"]).update(expires_at=now - timedelta(seconds=1))
        self.fail(count=5)
        LoginSecurityState.objects.update(updated_at=now - timedelta(days=2))
        _cleanup(now)
        self.assertFalse(LoginChallenge.objects.exists())
        self.assertEqual(LoginSecurityState.objects.filter(scope="login_pair").count(), 1)
        self.assertEqual(LoginSecurityState.objects.get(scope="login_pair").attempts, 5)


@override_settings(LOGIN_MAX_FAILURES=5, LOGIN_IP_MAX_FAILURES=20)
class ConcurrentLoginSecurityTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_parallel_attempts_are_serialized_and_cannot_pass_the_threshold(self):
        barrier = Barrier(8)

        def attempt(_):
            close_old_connections()
            request = RequestFactory().post("/api/auth/login/", REMOTE_ADDR="192.0.2.77")
            try:
                barrier.wait(timeout=10)
                with login_attempt(request, "parallel-user"):
                    state = get_login_state(request, "parallel-user")
                    if state["retry_after"]:
                        return "blocked"
                    record_login_failure(request, "parallel-user")
                    return "checked"
            finally:
                connection.close()

        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(attempt, range(8)))
        self.assertEqual(results.count("checked"), 5)
        self.assertEqual(results.count("blocked"), 3)
        self.assertEqual(LoginSecurityState.objects.get(scope="login_pair").attempts, 5)
        self.assertEqual(LoginSecurityState.objects.get(scope="login_source").attempts, 5)
