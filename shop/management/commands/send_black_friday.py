"""
Sends the Black Friday notification to every active customer:
    python manage.py send_black_friday
Your own message to everyone:
    python manage.py send_black_friday --en "Text" --ru "Текст" --kk "Мәтін" --link /catalog
"""
from django.core.management.base import BaseCommand

from shop.services import BLACK_FRIDAY, broadcast_notification


class Command(BaseCommand):
    help = "Send the Black Friday (or any) notification to all customers"

    def add_arguments(self, parser):
        parser.add_argument("--en", default=BLACK_FRIDAY["en"])
        parser.add_argument("--ru", default=BLACK_FRIDAY["ru"])
        parser.add_argument("--kk", default=BLACK_FRIDAY["kk"])
        parser.add_argument("--link", default="/catalog")

    def handle(self, *args, **o):
        n = broadcast_notification(o["en"], o["ru"], o["kk"], link=o["link"])
        self.stdout.write(self.style.SUCCESS(f"Notification sent to {n} customers."))
