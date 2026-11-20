"""Run local Telegram account-linking updates without a public webhook."""
import re
import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop.telegram_client import TelegramUnavailable, get_updates
from .check_telegram import check_bot


def _link_update(update):
    if not isinstance(update, dict):
        return False
    message = update.get("message")
    if not isinstance(message, dict):
        return False
    chat = message.get("chat")
    if not isinstance(chat, dict) or chat.get("type") != "private":
        return False
    text = message.get("text")
    if not isinstance(text, str):
        return False
    parts = text.split()
    if not parts or parts[0].casefold() not in (
        "/start", f"/start@{settings.TELEGRAM_BOT_USERNAME}".casefold(),
    ):
        return False
    return len(parts) == 1 or (len(parts) == 2 and bool(re.fullmatch(r"link_[A-Za-z0-9_-]{20,59}", parts[1])))


class Command(BaseCommand):
    help = "Process private Telegram linking messages. Keep this running alongside Django."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Read one update batch without long polling.")

    def handle(self, *args, **options):
        check_bot()
        from shop.telegram_recovery import process_update

        offset = None
        once = options["once"]
        self.stdout.write("Telegram linking bot started. Press Ctrl+C to stop.")
        try:
            while True:
                try:
                    updates = get_updates(offset=offset, timeout=0 if once else 20)
                    for update in updates:
                        update_id = update.get("update_id") if isinstance(update, dict) else None
                        if not isinstance(update_id, int) or isinstance(update_id, bool):
                            continue
                        if offset is not None and update_id < offset:
                            continue
                        if _link_update(update):
                            process_update(update)
                        # A failed handler never advances the acknowledgement.
                        offset = update_id + 1
                except TelegramUnavailable:
                    if once:
                        raise CommandError("Telegram is temporarily unavailable. No update was acknowledged.") from None
                    self.stderr.write("Telegram is temporarily unavailable; retrying shortly.")
                    time.sleep(5)
                except Exception:
                    if once:
                        raise CommandError("Could not process Telegram updates. No failed update was acknowledged.") from None
                    self.stderr.write("Could not process a Telegram update; retrying shortly.")
                    time.sleep(5)
                if once:
                    break
        except KeyboardInterrupt:
            self.stdout.write("Telegram linking bot stopped.")
