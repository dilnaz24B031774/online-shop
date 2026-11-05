"""
Writes the RU/KK (and missing EN) descriptions into products that already exist,
without deleting any data:   python manage.py fill_descriptions
"""
from django.core.management.base import BaseCommand

from shop.models import Product
from .descriptions import DESCRIPTIONS


class Command(BaseCommand):
    help = "Fill product descriptions in English, Russian and Kazakh"

    def handle(self, *args, **opts):
        updated = 0
        for product in Product.objects.filter(sku__in=DESCRIPTIONS.keys()):
            en, ru, kk = DESCRIPTIONS[product.sku]
            if en:
                product.description_en = en
            product.description_ru = ru
            product.description_kk = kk
            product.save(update_fields=["description_en", "description_ru", "description_kk"])
            updated += 1
        self.stdout.write(self.style.SUCCESS(f"Descriptions updated for {updated} products."))
