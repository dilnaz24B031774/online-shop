"""Email recovery using Django's expiring, password-bound reset tokens."""
from datetime import timedelta
import logging
import math
import smtplib

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import EmailMultiAlternatives, get_connection
from django.db import transaction
from django.template import loader
from django.utils import timezone
from django.utils.crypto import salted_hmac
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from .models import LoginSecurityState, User

logger = logging.getLogger(__name__)


def email_delivery_configured():
    backend = settings.EMAIL_BACKEND
    if backend in (
        "django.core.mail.backends.console.EmailBackend",
        "django.core.mail.backends.filebased.EmailBackend",
        "django.core.mail.backends.dummy.EmailBackend",
    ):
        return False
    if backend == "django.core.mail.backends.smtp.EmailBackend":
        if not settings.EMAIL_HOST:
            return False
        if settings.EMAIL_HOST.lower() == "smtp.gmail.com":
            return bool(settings.EMAIL_HOST_USER.strip() and settings.EMAIL_HOST_PASSWORD.strip())
    return True


class DeliveryCheckedResetForm(PasswordResetForm):
    """Reuse the verified transport and let delivery failures reach the caller."""

    def __init__(self, *args, connection, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection = connection

    def send_mail(self, subject_template_name, email_template_name, context,
                  from_email, to_email, html_email_template_name=None):
        subject = "".join(loader.render_to_string(subject_template_name, context).splitlines())
        body = loader.render_to_string(email_template_name, context)
        message = EmailMultiAlternatives(subject, body, from_email, [to_email], connection=self.connection)
        if html_email_template_name:
            message.attach_alternative(loader.render_to_string(html_email_template_name, context), "text/html")
        if message.send() != 1:
            raise smtplib.SMTPException("Password recovery email was not accepted.")


class ResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=254)


class ResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=64, write_only=True)
    token = serializers.CharField(max_length=128, write_only=True)
    new_password = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)
    new_password_confirm = serializers.CharField(max_length=4096, trim_whitespace=False, write_only=True)


def _response(body, status=200, retry_after=0):
    response = Response(body, status=status)
    response["Cache-Control"] = "no-store"
    if retry_after:
        response["Retry-After"] = str(retry_after)
    return response


@transaction.atomic
def _rate_limit(request, email=None):
    """Share bounded counters across workers without touching login failures.

    Count every email, including unknown accounts, identically. Acquire the
    source bucket first so a blocked source cannot allocate arbitrary rows.
    """
    now = timezone.now()
    window = max(1, settings.PASSWORD_RESET_RATE_WINDOW)
    source = str(request.META.get("REMOTE_ADDR", "unknown"))[:128]
    scopes = [("reset_source", source, settings.PASSWORD_RESET_IP_LIMIT)] if email is not None else [
        ("reset_confirm", source, settings.PASSWORD_RESET_CONFIRM_LIMIT),
    ]
    if email is not None:
        scopes.append(("reset_email", email.casefold(), settings.PASSWORD_RESET_EMAIL_LIMIT))
    for scope, value, limit in scopes:
        key = salted_hmac("shop.password_reset." + scope, value, algorithm="sha256").hexdigest()
        bucket, _ = LoginSecurityState.objects.select_for_update().get_or_create(
            key=key, defaults={"scope": scope, "window_started_at": now},
        )
        deadline = bucket.window_started_at + timedelta(seconds=window)
        if now >= deadline:
            bucket.attempts = 0
            bucket.window_started_at = now
            deadline = now + timedelta(seconds=window)
        if bucket.attempts >= max(1, limit):
            return max(1, math.ceil((deadline - now).total_seconds()))
        bucket.attempts += 1
        bucket.save(update_fields=["attempts", "window_started_at", "updated_at"])
    return 0


def _limited(retry_after):
    return _response({
        "code": "password_reset_rate_limited",
        "detail": "Too many requests. Please try again later.",
    }, status=429, retry_after=retry_after)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def request_reset(request):
    serializer = ResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return _response(serializer.errors, status=400)
    if not email_delivery_configured():
        return _response({
            "code": "email_not_configured",
            "detail": "Email sending is currently unavailable. Please try again later.",
        }, status=503)
    email = serializer.validated_data["email"]
    retry_after = _rate_limit(request, email)
    if retry_after:
        return _limited(retry_after)

    # Never construct recovery links from the caller's Host or Origin header.
    # Open/authenticate even for unknown accounts: an unavailable SMTP service
    # must return the same error without revealing whether an email exists.
    try:
        with get_connection(fail_silently=False) as connection:
            form = DeliveryCheckedResetForm({"email": email}, connection=connection)
            if not form.is_valid():
                return _response(dict(form.errors), status=400)
            form.save(
                domain_override="SaudaGo",
                from_email=settings.DEFAULT_FROM_EMAIL,
                subject_template_name="shop/password_reset_subject.txt",
                email_template_name="shop/password_reset_email.txt",
                extra_email_context={
                    "frontend_url": settings.FRONTEND_URL.rstrip("/"),
                    "expires_minutes": math.ceil(settings.PASSWORD_RESET_TIMEOUT / 60),
                },
            )
    except smtplib.SMTPRecipientsRefused:
        # A mailbox-specific rejection must not reveal that the submitted
        # address belongs to an account. Keep its response identical to an
        # unknown email; administrators can inspect the delivery error.
        logger.exception("Password recovery email recipient was refused.")
    except (smtplib.SMTPException, OSError, ValueError):
        logger.exception("Password recovery email service failed.")
        return _response({
            "code": "email_delivery_failed",
            "detail": "We could not send the email right now. Please try again later.",
        }, status=503)
    return _response({"detail": "If an active account uses this email, a password reset link has been sent."})


def _invalid_link():
    return _response({
        "code": "invalid_reset_link",
        "detail": "This password reset link is invalid or expired. Please request a new one.",
    }, status=400)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def confirm_reset(request):
    retry_after = _rate_limit(request)
    if retry_after:
        return _limited(retry_after)
    serializer = ResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return _response(serializer.errors, status=400)
    data = serializer.validated_data
    try:
        uid = int(urlsafe_base64_decode(data["uid"]).decode())
        if not 0 < uid <= 9223372036854775807:
            return _invalid_link()
    except (ValueError, UnicodeError, OverflowError):
        return _invalid_link()

    # Check and consume while locking the user, so a link cannot be used twice
    # by simultaneous requests. Saving the hash also revokes existing JWTs.
    with transaction.atomic():
        user = User.objects.select_for_update().filter(pk=uid, is_active=True).first()
        if user is None or not user.has_usable_password() or not default_token_generator.check_token(user, data["token"]):
            return _invalid_link()
        password = data["new_password"]
        if password != data["new_password_confirm"]:
            return _response({"new_password_confirm": ["The passwords do not match."]}, status=400)
        if user.check_password(password):
            return _response({"new_password": ["Choose a password different from your current password."]}, status=400)
        try:
            validate_password(password, user=user)
        except ValidationError as error:
            return _response({"new_password": error.messages}, status=400)
        user.set_password(password)
        user.save(update_fields=["password"])
    return _response({"detail": "Password updated successfully. Sign in with your new password."})
