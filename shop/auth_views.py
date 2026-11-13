"""Public authentication endpoints with persistent, shared login protection."""
from collections.abc import Mapping

from rest_framework import exceptions
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .login_security import (
    SecurityRateLimited, get_login_state, issue_challenge, login_attempt,
    record_login_failure, record_login_success, verify_challenge,
)


def _response(body, status=200, retry_after=0):
    response = Response(body, status=status)
    response["Cache-Control"] = "no-store"
    if retry_after:
        response["Retry-After"] = str(retry_after)
    return response


def _rejected(state, *, challenge=False):
    if state["retry_after"]:
        return _response({
            **state, "code": "login_locked",
            "detail": "Слишком много неудачных попыток. Вход временно заблокирован.",
        }, status=429, retry_after=state["retry_after"])
    return _response({
        **state, "code": "challenge_required" if challenge else "invalid_credentials",
        "detail": ("Пройдите новую проверку и повторите вход." if challenge
                   else "Неверный логин или пароль."),
    }, status=400 if challenge else 401)


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def login(request):
    payload = request.data if isinstance(request.data, Mapping) else {}
    raw_username = payload.get("username", "")
    username = raw_username.strip() if isinstance(raw_username, str) else ""
    password = payload.get("password", "")
    with login_attempt(request, username):
        state = get_login_state(request, username)
        if state["retry_after"]:
            return _rejected(state)
        # Automated form fillers often populate this off-screen decoy field.
        if payload.get("website"):
            return _rejected(record_login_failure(request, username))
        if state["challenge_required"] and not verify_challenge(
            request, payload.get("challenge_id"), payload.get("challenge_answer"),
        ):
            return _rejected(record_login_failure(request, username), challenge=True)
        if not username or len(username) > 150 or not isinstance(password, str) or not 1 <= len(password) <= 4096:
            return _rejected(record_login_failure(request, username))
        serializer = TokenObtainPairSerializer(
            data={"username": username, "password": password},
            context={"request": request},
        )
        try:
            serializer.is_valid(raise_exception=True)
        except (exceptions.AuthenticationFailed, exceptions.ValidationError):
            return _rejected(record_login_failure(request, username))
        record_login_success(request, username)
        return _response(serializer.validated_data)


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
def challenge(request):
    state = get_login_state(request, "")
    if state["retry_after"]:
        return _rejected(state)
    # Only the login flow currently consumes these challenges publicly.
    if request.query_params.get("purpose", "login") != "login":
        return _response({"detail": "Неизвестный тип проверки."}, status=400)
    try:
        return _response(issue_challenge(request))
    except SecurityRateLimited as error:
        return _response({
            "code": "challenge_rate_limited", "detail": error.detail,
            "retry_after": error.retry_after,
        }, status=429, retry_after=error.retry_after)
