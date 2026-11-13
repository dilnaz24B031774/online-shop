"""Persistent login throttling and a small, local anti-automation challenge.

Throttling is the primary control. Arithmetic challenges add friction, but are
not equivalent to a managed CAPTCHA service. Never trust a forwarding header
unless a trusted reverse proxy has first validated and replaced REMOTE_ADDR.
"""
from contextlib import contextmanager
from datetime import timedelta
import ipaddress
import math
import secrets
import unicodedata

from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .models import LoginChallenge, LoginSecurityState


class SecurityRateLimited(Exception):
    def __init__(self, retry_after, detail="Слишком много попыток. Попробуйте позже."):
        self.retry_after = max(1, int(retry_after))
        self.detail = detail
        super().__init__(detail)


def _setting(name, default):
    return max(1, int(getattr(settings, name, default)))


def _hash(kind, value):
    return salted_hmac("shop.login_security." + kind, value, algorithm="sha256").hexdigest()


def _source(request):
    value = str(request.META.get("REMOTE_ADDR", "unknown"))[:128]
    try:
        return str(ipaddress.ip_address(value))
    except ValueError:
        return value


def _keys(request, username):
    source = _source(request)
    normalized = unicodedata.normalize("NFKC", str(username or "")[:512]).strip().casefold()
    return _hash("source", source), _hash("pair", source + "\x00" + normalized)


def _locked_bucket(key, scope, now):
    # The unique primary key plus get_or_create's savepoint handles a competing
    # first insert; select_for_update also applies to its retry after a conflict.
    bucket, _ = LoginSecurityState.objects.select_for_update().get_or_create(
        key=key, defaults={"scope": scope, "window_started_at": now},
    )
    return bucket


def _retry_after(bucket, now):
    if bucket is not None and bucket.locked_until and bucket.locked_until > now:
        return max(1, math.ceil((bucket.locked_until - now).total_seconds()))
    return 0


def _effective_attempts(bucket, now, window):
    if bucket is None:
        return 0
    if _retry_after(bucket, now):
        return bucket.attempts
    if bucket.locked_until is not None or now >= bucket.window_started_at + timedelta(seconds=window):
        return 0
    return bucket.attempts


def _state(source_bucket, pair_bucket, now):
    window = _setting("LOGIN_FAILURE_WINDOW_SECONDS", 300)
    pair_limit = _setting("LOGIN_MAX_FAILURES", 5)
    source_limit = _setting("LOGIN_IP_MAX_FAILURES", 20)
    pair_count = _effective_attempts(pair_bucket, now, window)
    source_count = _effective_attempts(source_bucket, now, window)
    retry_after = max(_retry_after(source_bucket, now), _retry_after(pair_bucket, now))
    return {
        "retry_after": retry_after,
        "challenge_required": not retry_after and (
            pair_count >= _setting("LOGIN_CHALLENGE_AFTER", 3)
            or source_count >= _setting("LOGIN_IP_CHALLENGE_AFTER", 10)
        ),
        "remaining_attempts": max(0, min(pair_limit - pair_count, source_limit - source_count)),
    }


def get_login_state(request, username):
    """Read without allocating rows for arbitrary username/status probes."""
    source_key, pair_key = _keys(request, username)
    buckets = LoginSecurityState.objects.in_bulk([source_key, pair_key])
    return _state(buckets.get(source_key), buckets.get(pair_key), timezone.now())


@contextmanager
def login_attempt(request, username):
    """Keep the check, password validation, and accounting in one transaction.

    Both the API and the admin login must use this guard. Always acquire the
    source before the account/source pair, including nested accounting calls.
    """
    with transaction.atomic():
        now = timezone.now()
        source_key, pair_key = _keys(request, username)
        source_bucket = _locked_bucket(source_key, "login_source", now)
        # A blocked source must not allocate a fresh row for every random name
        # sent by a bot during the lockout.
        if not _retry_after(source_bucket, now):
            _locked_bucket(pair_key, "login_pair", now)
        yield


def _increment(bucket, now, window, limit, lock_seconds):
    if _retry_after(bucket, now):
        # Requests made during a lock do not push the unlock time into the future.
        return
    effective = _effective_attempts(bucket, now, window)
    if effective == 0:
        bucket.window_started_at = now
    bucket.attempts = effective + 1
    bucket.locked_until = now + timedelta(seconds=lock_seconds) if bucket.attempts >= limit else None
    bucket.save(update_fields=["attempts", "window_started_at", "locked_until", "updated_at"])


@transaction.atomic
def record_login_failure(request, username):
    now = timezone.now()
    source_key, pair_key = _keys(request, username)
    source_bucket = _locked_bucket(source_key, "login_source", now)
    if _retry_after(source_bucket, now):
        return _state(source_bucket, None, now)
    pair_bucket = _locked_bucket(pair_key, "login_pair", now)
    # A caller may conservatively record every rejected request. Preserve all
    # counters while either scope is locked, so traffic cannot extend the lock.
    if _retry_after(source_bucket, now) or _retry_after(pair_bucket, now):
        return _state(source_bucket, pair_bucket, now)
    window = _setting("LOGIN_FAILURE_WINDOW_SECONDS", 300)
    lock_seconds = _setting("LOGIN_LOCKOUT_SECONDS", 300)
    _increment(source_bucket, now, window, _setting("LOGIN_IP_MAX_FAILURES", 20), lock_seconds)
    _increment(pair_bucket, now, window, _setting("LOGIN_MAX_FAILURES", 5), lock_seconds)
    return _state(source_bucket, pair_bucket, now)


@transaction.atomic
def record_login_success(request, username):
    """Reset this account/source pair, retaining source-wide spraying history."""
    now = timezone.now()
    source_key, pair_key = _keys(request, username)
    source_bucket = _locked_bucket(source_key, "login_source", now)
    if _retry_after(source_bucket, now):
        raise SecurityRateLimited(_retry_after(source_bucket, now))
    pair_bucket = _locked_bucket(pair_key, "login_pair", now)
    state = _state(source_bucket, pair_bucket, now)
    if state["retry_after"]:
        raise SecurityRateLimited(state["retry_after"])
    pair_bucket.attempts = 0
    pair_bucket.window_started_at = now
    pair_bucket.locked_until = None
    pair_bucket.save(update_fields=["attempts", "window_started_at", "locked_until", "updated_at"])


@transaction.atomic
def _cleanup(now):
    """Bound maintenance work; active locks are never removed."""
    challenge_rows = LoginChallenge.objects.filter(expires_at__lte=now)
    state_rows = LoginSecurityState.objects.all()
    if connection.features.has_select_for_update_skip_locked:
        # Do not wait on in-flight logins. In particular, never acquire a pair
        # while waiting for its source in the opposite order to login_attempt.
        challenge_rows = challenge_rows.select_for_update(skip_locked=True)
        state_rows = state_rows.select_for_update(skip_locked=True)
    expired = list(challenge_rows.values_list("pk", flat=True)[:100])
    if expired:
        LoginChallenge.objects.filter(pk__in=expired, expires_at__lte=now).delete()
    stale_before = now - timedelta(days=1)
    stale = list(state_rows.filter(updated_at__lt=stale_before).filter(
        Q(locked_until__isnull=True) | Q(locked_until__lte=now),
    ).values_list("pk", flat=True)[:100])
    if stale:
        # Reapply timestamps after waiting for a row lock, because another request
        # may have updated a candidate since the preliminary bounded query.
        LoginSecurityState.objects.filter(pk__in=stale, updated_at__lt=stale_before).filter(
            Q(locked_until__isnull=True) | Q(locked_until__lte=now),
        ).delete()


def issue_challenge(request, purpose="login"):
    if purpose not in ("login", "register"):
        raise ValueError("Unknown challenge purpose")
    now = timezone.now()
    source_key = _hash("source", _source(request))
    issuance_key = _hash("challenge_issuance", _source(request))
    with transaction.atomic():
        bucket = _locked_bucket(issuance_key, "challenge_issuance", now)
        window_seconds = 60
        limit = _setting("CHALLENGE_MAX_ISSUED_PER_MINUTE", 20)
        count = _effective_attempts(bucket, now, window_seconds)
        if count >= limit:
            remaining = math.ceil((bucket.window_started_at + timedelta(seconds=window_seconds) - now).total_seconds())
            raise SecurityRateLimited(remaining, "Слишком много проверок. Подождите минуту.")
        if count == 0:
            bucket.window_started_at = now
        bucket.attempts = count + 1
        bucket.save(update_fields=["attempts", "window_started_at", "updated_at"])
        left, right = secrets.randbelow(19) + 1, secrets.randbelow(19) + 1
        challenge_id = secrets.token_urlsafe(32)
        lifetime = min(120, _setting("LOGIN_CHALLENGE_TTL_SECONDS", 120))
        LoginChallenge.objects.create(
            id=challenge_id, source_key=source_key, purpose=purpose,
            answer_digest=_hash("challenge_answer", challenge_id + "\x00" + str(left + right)),
            expires_at=now + timedelta(seconds=lifetime),
        )
    if secrets.randbelow(32) == 0:
        _cleanup(now)
    return {"id": challenge_id, "prompt": f"{left} + {right} = ?", "expires_in": lifetime}


@transaction.atomic
def verify_challenge(request, challenge_id, answer, purpose="login"):
    if not isinstance(challenge_id, str) or not 20 <= len(challenge_id) <= 64:
        return False
    challenge = LoginChallenge.objects.select_for_update().filter(pk=challenge_id).first()
    if challenge is None:
        return False
    # Every verification consumes its nonce, even a wrong answer/source/purpose.
    challenge.delete()
    text = str(answer if answer is not None else "").strip()
    valid_answer = bool(text) and len(text) <= 3 and text.isascii() and text.isdecimal()
    normalized = str(int(text)) if valid_answer else "invalid"
    digest = _hash("challenge_answer", challenge_id + "\x00" + normalized)
    answer_matches = constant_time_compare(digest, challenge.answer_digest)
    source_matches = constant_time_compare(_hash("source", _source(request)), challenge.source_key)
    return (
        valid_answer and answer_matches and source_matches
        and challenge.purpose == purpose and challenge.expires_at > timezone.now()
    )
