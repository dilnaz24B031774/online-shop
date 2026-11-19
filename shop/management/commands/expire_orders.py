"""
Cancel unpaid QR / bank transfer orders whose payment time is over.
    python manage.py expire_orders            # once
    python manage.py expire_orders --loop     # every 30 seconds (leave it running during the demo)
The website also does this check by itself when orders are opened, so the command is optional.
"""
import time

from django.core.management.base import BaseCommand

from shop.services import expire_unpaid_orders


class Command(BaseCommand):
    help = "Cancel orders that were not paid in time"

    def add_arguments(self, parser):
        parser.add_argument("--loop", action="store_true", help="repeat every 30 seconds")

    def handle(self, *args, **opts):
        while True:
            n = expire_unpaid_orders()
            self.stdout.write(self.style.SUCCESS(f"Cancelled unpaid orders: {n}"))
            if not opts["loop"]:
                break
            time.sleep(30)
