"""Check bot credentials without sending a message or changing webhooks."""
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from shop.telegram_client import TelegramUnavailable, configured, get_me, get_webhook_info


def check_bot():
    if not configured():
        raise CommandError("Fill TELEGRAM_BOT_TOKEN and TELEGRAM_BOT_USERNAME in .env.")
    try:
        bot = get_me()
        if str(bot.get("username", "")).casefold() != settings.TELEGRAM_BOT_USERNAME.casefold():
            raise CommandError("The bot token and configured username refer to different bots.")
        if get_webhook_info().get("url"):
            raise CommandError("This bot has an active webhook. Use a separate bot for local polling, or remove the webhook yourself.")
    except TelegramUnavailable:
        raise CommandError("Could not verify the Telegram bot. Check its credentials and network connection.") from None


class Command(BaseCommand):
    help = "Verify Telegram credentials and polling availability without sending messages."

    def handle(self, *args, **options):
        check_bot()
        self.stdout.write(self.style.SUCCESS("Telegram bot verified. No message was sent."))
