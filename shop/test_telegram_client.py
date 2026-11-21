"""Transport and polling safety; no real Telegram network requests are made."""
from io import BytesIO, StringIO
import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock, call, patch
from urllib.error import HTTPError

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, override_settings

from . import telegram_client
from .management.commands.run_telegram_bot import _link_update


TOKEN = "123456:" + "x" * 30


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_BOT_USERNAME="sauda_recovery_bot", TELEGRAM_REQUEST_TIMEOUT=10)
class TelegramTransportTests(SimpleTestCase):
    def response(self, result):
        return BytesIO(json.dumps({"ok": True, "result": result}).encode())

    def test_missing_or_malformed_configuration_never_opens_network(self):
        for token, username in (("", "sauda_recovery_bot"), (TOKEN, ""), (TOKEN, "bad/name"), ("bad/token", "sauda_recovery_bot")):
            with self.settings(TELEGRAM_BOT_TOKEN=token, TELEGRAM_BOT_USERNAME=username), patch.object(telegram_client._opener, "open") as network:
                self.assertFalse(telegram_client.configured())
                with self.assertRaises(telegram_client.TelegramUnavailable):
                    telegram_client.get_me()
                network.assert_not_called()

    def test_messages_use_https_json_and_protected_content(self):
        with patch.object(telegram_client._opener, "open", return_value=self.response({"message_id": 1})) as network:
            result = telegram_client.send_message(1234, "Test code")
        request = network.call_args.args[0]
        self.assertTrue(request.full_url.startswith("https://api.telegram.org/bot"))
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(json.loads(request.data), {
            "chat_id": 1234, "text": "Test code", "protect_content": True,
            "link_preview_options": {"is_disabled": True},
        })
        self.assertEqual(result, {"message_id": 1})

    def test_upstream_errors_do_not_expose_token_url_or_response(self):
        secret_url = f"https://api.telegram.org/bot{TOKEN}/getMe"
        error = HTTPError(secret_url, 401, "private upstream body", None, None)
        with patch.object(telegram_client._opener, "open", side_effect=error):
            with self.assertRaises(telegram_client.TelegramUnavailable) as caught:
                telegram_client.get_me()
        self.assertNotIn(TOKEN, str(caught.exception))
        self.assertNotIn(secret_url, str(caught.exception))
        self.assertNotIn("private upstream body", str(caught.exception))
        self.assertIsNone(caught.exception.__cause__)

    def test_redirects_are_not_followed(self):
        self.assertIsNone(telegram_client._NoRedirect().redirect_request(
            None, None, 302, "redirect", {}, "https://attacker.example/",
        ))

    def test_unaccepted_and_malformed_responses_are_rejected(self):
        for body in (b"not JSON", b"[]", b'{"ok": false, "description": "secret"}', b'{"ok": true}'):
            with patch.object(telegram_client._opener, "open", return_value=BytesIO(body)):
                with self.assertRaises(telegram_client.TelegramUnavailable):
                    telegram_client.get_me()
        with patch.object(telegram_client._opener, "open", return_value=self.response(False)):
            with self.assertRaises(telegram_client.TelegramUnavailable):
                telegram_client.send_message(1234, "Code")

    def test_polling_is_bounded_and_requests_only_messages(self):
        with patch.object(telegram_client._opener, "open", return_value=self.response([])) as network:
            self.assertEqual(telegram_client.get_updates(offset=123, timeout=120), [])
        self.assertEqual(json.loads(network.call_args.args[0].data), {
            "offset": 123, "timeout": 20, "limit": 50, "allowed_updates": ["message"],
        })
        self.assertEqual(network.call_args.kwargs["timeout"], 30)


@override_settings(TELEGRAM_BOT_TOKEN=TOKEN, TELEGRAM_BOT_USERNAME="sauda_recovery_bot", TELEGRAM_REQUEST_TIMEOUT=10)
class TelegramCommandTests(SimpleTestCase):
    def update(self, update_id, text="/start"):
        return {"update_id": update_id, "message": {"chat": {"type": "private"}, "text": text}}

    def test_bot_check_validates_identity_without_messages_or_updates(self):
        with patch("shop.management.commands.check_telegram.get_me", return_value={"username": "Sauda_Recovery_Bot"}), patch(
            "shop.management.commands.check_telegram.get_webhook_info", return_value={"url": ""},
        ), patch("shop.telegram_client.send_message") as send, patch("shop.telegram_client.get_updates") as updates:
            output = StringIO()
            call_command("check_telegram", stdout=output)
        self.assertIn("No message was sent", output.getvalue())
        send.assert_not_called()
        updates.assert_not_called()

    def test_bot_check_refuses_mismatched_identity_or_existing_webhook(self):
        for username, webhook in (("other_bot", ""), ("sauda_recovery_bot", "https://existing.example/webhook")):
            with patch("shop.management.commands.check_telegram.get_me", return_value={"username": username}), patch(
                "shop.management.commands.check_telegram.get_webhook_info", return_value={"url": webhook},
            ):
                with self.assertRaises(CommandError):
                    call_command("check_telegram", stdout=StringIO())

    def test_only_private_start_commands_are_forwarded(self):
        self.assertTrue(_link_update(self.update(1)))
        self.assertTrue(_link_update(self.update(1, "/start@sauda_recovery_bot")))
        self.assertTrue(_link_update(self.update(1, "/start link_" + "a" * 43)))
        for update in (
            self.update(1, "/start@other_bot"), self.update(1, "/reset"), self.update(1, "hello"),
            {"update_id": 1, "message": {"chat": {"type": "group"}, "text": "/start link_" + "a" * 43}},
        ):
            self.assertFalse(_link_update(update))

    def test_failed_update_is_not_acknowledged_by_offset(self):
        handler = Mock(side_effect=[None, telegram_client.TelegramUnavailable("Unavailable")])
        module = SimpleNamespace(process_update=handler)
        with patch.dict(sys.modules, {"shop.telegram_recovery": module}), patch(
            "shop.management.commands.run_telegram_bot.check_bot",
        ), patch("shop.management.commands.run_telegram_bot.get_updates", side_effect=[
            [self.update(1), self.update(2)], KeyboardInterrupt,
        ]) as updates, patch("shop.management.commands.run_telegram_bot.time.sleep"):
            call_command("run_telegram_bot", stdout=StringIO(), stderr=StringIO())
        self.assertEqual(updates.call_args_list, [call(offset=None, timeout=20), call(offset=2, timeout=20)])
        self.assertEqual(handler.call_count, 2)

    def test_once_does_not_wait_and_ignores_unsupported_updates(self):
        handler = Mock()
        with patch.dict(sys.modules, {"shop.telegram_recovery": SimpleNamespace(process_update=handler)}), patch(
            "shop.management.commands.run_telegram_bot.check_bot",
        ), patch("shop.management.commands.run_telegram_bot.get_updates", return_value=[self.update(1, "hello")]) as updates:
            call_command("run_telegram_bot", once=True, stdout=StringIO())
        updates.assert_called_once_with(offset=None, timeout=0)
        handler.assert_not_called()
