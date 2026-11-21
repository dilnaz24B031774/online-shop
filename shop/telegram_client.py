"""Small Telegram Bot API transport; upstream URLs and tokens stay private."""
import json
import re
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from django.conf import settings


class TelegramUnavailable(Exception):
    """A safe public error without credentials or Telegram response contents."""


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # Bot credentials are part of the URL. Never forward them on redirects.
        return None


_opener = build_opener(_NoRedirect)
_username = re.compile(r"[A-Za-z][A-Za-z0-9_]{4,31}\Z")
_token = re.compile(r"[0-9]+:[A-Za-z0-9_-]{20,}\Z")


def configured():
    return bool(
        _token.fullmatch(getattr(settings, "TELEGRAM_BOT_TOKEN", ""))
        and _username.fullmatch(getattr(settings, "TELEGRAM_BOT_USERNAME", ""))
    )


def call(method, payload=None, timeout=None):
    if not configured() or not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", method):
        raise TelegramUnavailable("Telegram is not configured.")
    request = Request(
        f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/{method}",
        data=json.dumps(payload or {}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with _opener.open(request, timeout=timeout or settings.TELEGRAM_REQUEST_TIMEOUT) as response:
            # getUpdates is bounded to 50 updates, each with a bounded message.
            body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise TelegramUnavailable("Telegram returned an invalid response.")
        result = json.loads(body)
    except (HTTPError, URLError, HTTPException, OSError, ValueError, UnicodeError):
        raise TelegramUnavailable("Telegram is temporarily unavailable.") from None
    if not isinstance(result, dict) or result.get("ok") is not True or "result" not in result:
        raise TelegramUnavailable("Telegram is temporarily unavailable.")
    return result["result"]


def get_me():
    result = call("getMe")
    if not isinstance(result, dict) or result.get("is_bot") is not True:
        raise TelegramUnavailable("Telegram returned an invalid bot identity.")
    return result


def get_webhook_info():
    result = call("getWebhookInfo")
    if not isinstance(result, dict):
        raise TelegramUnavailable("Telegram returned an invalid webhook status.")
    return result


def get_updates(offset=None, timeout=20):
    seconds = max(0, min(20, int(timeout)))
    payload = {"timeout": seconds, "limit": 50, "allowed_updates": ["message"]}
    if offset is not None:
        payload["offset"] = int(offset)
    result = call("getUpdates", payload, timeout=max(settings.TELEGRAM_REQUEST_TIMEOUT, seconds + 10))
    if not isinstance(result, list):
        raise TelegramUnavailable("Telegram returned invalid updates.")
    return result


def send_message(chat_id, text):
    result = call("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "protect_content": True,
        "link_preview_options": {"is_disabled": True},
    })
    if not isinstance(result, dict) or not isinstance(result.get("message_id"), int):
        raise TelegramUnavailable("Telegram did not accept the message.")
    return result
