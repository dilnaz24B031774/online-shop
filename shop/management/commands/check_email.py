"""Verify configured email transport without sending a message."""
from django.core.mail import get_connection
from django.core.management.base import BaseCommand, CommandError

from shop.password_reset import email_delivery_configured


class Command(BaseCommand):
    help = "Check email configuration and SMTP authentication without sending email."

    def handle(self, *args, **options):
        if not email_delivery_configured():
            raise CommandError("Email is not configured. Fill EMAIL_HOST_USER and EMAIL_HOST_PASSWORD in .env.")
        try:
            with get_connection(fail_silently=False):
                pass
        except Exception:
            raise CommandError("Could not connect or authenticate. Check email settings and the app password.") from None
        self.stdout.write(self.style.SUCCESS("Email connection and authentication succeeded. No message was sent."))
