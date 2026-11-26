"""Telegram is a recovery channel only after the signed-in owner links it."""
from datetime import timedelta
import logging
import re
import secrets

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated

from . import telegram_client
from .models import TelegramAccount, TelegramChallenge, User
from .password_reset import _limited, _rate_limit, _response

logger = logging.getLogger(__name__)
LIFETIME = 600
MAX_ATTEMPTS = 5
NONCE = re.compile(r"^[A-Za-z0-9_-]{43}$")


class CurrentPasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


class RecoveryRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254)


class RecoveryConfirmSerializer(serializers.Serializer):
    challenge_id = serializers.RegexField(NONCE, write_only=True)
    code = serializers.RegexField(r"^[0-9]{6}$", write_only=True)
    new_password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)
    new_password_confirm = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


def _digest(kind, value):
    return salted_hmac("shop.telegram_recovery." + kind, value, algorithm="sha256").hexdigest()


def _fingerprint(user, telegram_id=None):
    return _digest("password", user.password + ":" + str(telegram_id or ""))


def _unavailable(code="telegram_unavailable"):
    return _response({"code": code, "detail": "Telegram recovery is currently unavailable. Please try again later."}, status=503)


def _invalid_code():
    return _response({"code": "invalid_telegram_code", "detail": "The code is invalid or expired. Please request a new code."}, status=400)


def _check_bot():
    bot = telegram_client.get_me()
    if bot.get("is_bot") is not True or bot.get("username", "").casefold() != settings.TELEGRAM_BOT_USERNAME.casefold():
        raise telegram_client.TelegramUnavailable("Telegram bot configuration does not match.")


def _fresh_challenge(user, purpose, *, telegram_id=None, code=""):
    now = timezone.now()
    # A fresh request supersedes earlier requests for this account/purpose.
    if user:
        TelegramChallenge.objects.filter(user=user, purpose=purpose, consumed_at__isnull=True).update(consumed_at=now)
    raw = secrets.token_urlsafe(32)
    key = _digest("nonce", raw)
    challenge = TelegramChallenge.objects.create(
        key=key, user=user, purpose=purpose, expires_at=now + timedelta(seconds=LIFETIME),
        password_digest=_fingerprint(user, telegram_id) if user else "",
        code_digest=_digest("code", key + ":" + code) if code else "",
    )
    return raw, challenge


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def status(request):
    account = TelegramAccount.objects.filter(user=request.user).first()
    return _response({
        "configured": telegram_client.configured(), "linked": account is not None,
        "username": account.username or None if account else None,
        "linked_at": account.linked_at.isoformat() if account else None,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def start_link(request):
    data = CurrentPasswordSerializer(data=request.data)
    if not data.is_valid():
        return _response(data.errors, status=400)
    if not telegram_client.configured():
        return _unavailable("telegram_not_configured")
    retry = _rate_limit(request, "telegram-link:" + str(request.user.pk))
    if retry:
        return _limited(retry)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not user.check_password(data.validated_data["current_password"]):
            return _response({"current_password": ["The current password is incorrect."]}, status=400)
        if TelegramAccount.objects.filter(user=user).exists():
            return _response({"code": "telegram_already_linked", "detail": "Unlink the current Telegram account before linking another."}, status=409)
        try:
            _check_bot()
        except telegram_client.TelegramUnavailable:
            return _unavailable()
        raw, _ = _fresh_challenge(user, "link")
    return _response({"link_url": f"https://t.me/{settings.TELEGRAM_BOT_USERNAME}?start=link_{raw}", "expires_in": LIFETIME})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def unlink(request):
    data = CurrentPasswordSerializer(data=request.data)
    if not data.is_valid():
        return _response(data.errors, status=400)
    retry = _rate_limit(request, "telegram-unlink:" + str(request.user.pk))
    if retry:
        return _limited(retry)
    with transaction.atomic():
        user = User.objects.select_for_update().get(pk=request.user.pk)
        if not user.check_password(data.validated_data["current_password"]):
            return _response({"current_password": ["The current password is incorrect."]}, status=400)
        TelegramAccount.objects.filter(user=user).delete()
        TelegramChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=timezone.now())
    return _response({"detail": "Telegram has been unlinked."})


def _code_message(code, language):
    if language == "ru":
        return f"SaudaGo: код восстановления пароля — {code}.\nДействует 10 минут. Введите его на сайте магазина. Никому не сообщайте код. Если вы не запрашивали сброс пароля, проигнорируйте сообщение."
    if language == "kk":
        return f"SaudaGo: құпиясөзді қалпына келтіру коды — {code}.\n10 минут жарамды. Кодты дүкен сайтында енгізіңіз. Кодты ешкімге бермеңіз. Сұрауды сіз жібермесеңіз, хабарламаны елемеңіз."
    return f"SaudaGo password recovery code: {code}.\nValid for 10 minutes. Enter it on the shop website. Do not share it. If you did not request a reset, ignore this message."


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def request_reset(request):
    data = RecoveryRequestSerializer(data=request.data)
    if not data.is_valid():
        return _response(data.errors, status=400)
    if not telegram_client.configured():
        return _unavailable("telegram_not_configured")
    identifier = data.validated_data["identifier"]
    retry = _rate_limit(request, "telegram-reset:" + identifier.casefold())
    if retry:
        return _limited(retry)
    try:
        # Check transport for every identifier, independently of account existence.
        _check_bot()
    except telegram_client.TelegramUnavailable:
        return _unavailable()
    with transaction.atomic():
        matches = list(User.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier), is_active=True,
        ).values_list("pk", flat=True)[:2])
        user = User.objects.select_for_update().filter(pk=matches[0], is_active=True).first() if len(matches) == 1 else None
        account = TelegramAccount.objects.filter(user=user).first() if user and user.has_usable_password() else None
        code = f"{secrets.randbelow(1000000):06d}"
        raw, challenge = _fresh_challenge(user if account else None, "reset",
                                          telegram_id=account.telegram_id if account else None, code=code)
        if account:
            try:
                telegram_client.send_message(account.telegram_id, _code_message(code, user.preferred_language))
            except telegram_client.TelegramUnavailable:
                # Blocked bots and destination-specific failures must not disclose
                # a registered account or leave an undelivered code usable.
                challenge.consumed_at = timezone.now()
                challenge.save(update_fields=["consumed_at"])
                logger.warning("Telegram recovery message could not be delivered.")
    return _response({
        "challenge_id": raw, "expires_in": LIFETIME,
        "detail": "If this account has Telegram linked, a recovery code has been sent to it.",
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def confirm_reset(request):
    retry = _rate_limit(request)
    if retry:
        return _limited(retry)
    data = RecoveryConfirmSerializer(data=request.data)
    if not data.is_valid():
        if "challenge_id" in data.errors or "code" in data.errors:
            return _invalid_code()
        return _response(data.errors, status=400)
    values = data.validated_data
    key = _digest("nonce", values["challenge_id"])
    owner_id = TelegramChallenge.objects.filter(pk=key, purpose="reset").values_list("user_id", flat=True).first()
    with transaction.atomic():
        # Always acquire the user before its challenge, as linking/unlinking do.
        user = User.objects.select_for_update().filter(pk=owner_id, is_active=True).first() if owner_id else None
        challenge = TelegramChallenge.objects.select_for_update().filter(pk=key, purpose="reset").first()
        now = timezone.now()
        if not challenge or challenge.consumed_at or challenge.expires_at <= now or challenge.attempts >= MAX_ATTEMPTS:
            return _invalid_code()
        account = TelegramAccount.objects.filter(user=user).first() if user else None
        valid_state = bool(user and user.has_usable_password() and account and constant_time_compare(
            challenge.password_digest, _fingerprint(user, account.telegram_id),
        ))
        valid_code = constant_time_compare(challenge.code_digest, _digest("code", key + ":" + values["code"]))
        if not valid_state or not valid_code:
            challenge.attempts += 1
            if challenge.attempts >= MAX_ATTEMPTS:
                challenge.consumed_at = now
            challenge.save(update_fields=["attempts", "consumed_at"])
            return _invalid_code()
        password = values["new_password"]
        if password != values["new_password_confirm"]:
            return _response({"new_password_confirm": ["The passwords do not match."]}, status=400)
        if user.check_password(password):
            return _response({"new_password": ["Choose a password different from your current password."]}, status=400)
        try:
            validate_password(password, user=user)
        except ValidationError as error:
            return _response({"new_password": error.messages}, status=400)
        user.set_password(password)
        user.save(update_fields=["password"])
        TelegramChallenge.objects.filter(user=user, consumed_at__isnull=True).update(consumed_at=now)
    return _response({"detail": "Password updated successfully. Sign in with your new password."})


def _consume_link(raw, telegram_id, username):
    key = _digest("nonce", raw)
    owner_id = TelegramChallenge.objects.filter(pk=key, purpose="link").values_list("user_id", flat=True).first()
    if not owner_id:
        return False
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=owner_id, is_active=True).first()
        challenge = TelegramChallenge.objects.select_for_update().filter(pk=key, purpose="link").first()
        now = timezone.now()
        if not user or not challenge or challenge.consumed_at or challenge.expires_at <= now:
            return False
        challenge.consumed_at = now
        challenge.save(update_fields=["consumed_at"])
        if not user.has_usable_password() or not constant_time_compare(challenge.password_digest, _fingerprint(user)):
            return False
        if TelegramAccount.objects.filter(Q(user=user) | Q(telegram_id=telegram_id)).exists():
            return False
        try:
            with transaction.atomic():
                TelegramAccount.objects.create(user=user, telegram_id=telegram_id, username=username[:64])
        except IntegrityError:
            return False
        return True


def process_update(update):
    """Called only by our authenticated getUpdates worker, never a public route."""
    message = update.get("message", {}) if isinstance(update, dict) else {}
    if not isinstance(message, dict):
        return
    chat, sender = message.get("chat", {}), message.get("from", {})
    if not isinstance(chat, dict) or not isinstance(sender, dict):
        return
    chat_id, sender_id = chat.get("id"), sender.get("id")
    if (chat.get("type") != "private" or type(chat_id) is not int or type(sender_id) is not int
            or not 0 < chat_id <= 9223372036854775807 or chat_id != sender_id or sender.get("is_bot") is not False):
        return
    text = message.get("text", "")
    if not isinstance(text, str):
        return
    parts = text.strip().split(maxsplit=1)
    if not parts or parts[0].casefold() not in ("/start", "/start@" + settings.TELEGRAM_BOT_USERNAME.casefold()):
        return
    if len(parts) == 2 and parts[1].startswith("link_") and NONCE.fullmatch(parts[1][5:]):
        username = sender.get("username", "")
        success = _consume_link(parts[1][5:], chat_id, username if isinstance(username, str) else "")
        reply = ("Telegram привязан к вашему аккаунту SaudaGo. Теперь вы можете получать здесь коды восстановления пароля."
                 if success else "Ссылка привязки недействительна или уже использована. Создайте новую в настройках аккаунта SaudaGo. Если Telegram уже привязан, сначала отключите его в настройках.")
    else:
        reply = "Бот восстановления пароля SaudaGo. Сначала войдите в магазин и привяжите Telegram в настройках аккаунта. Затем используйте «Забыли пароль?» на сайте — код придёт в этот чат."
    try:
        telegram_client.send_message(chat_id, reply)
    except telegram_client.TelegramUnavailable:
        # Linking has already committed. Do not replay the consumed nonce just
        # because its acknowledgement could not be delivered; settings show
        # the authoritative status and the poller can acknowledge this update.
        logger.warning("Telegram bot acknowledgement could not be delivered.")
