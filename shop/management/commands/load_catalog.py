"""
Adds the new products, categories and photo galleries to the shop.
Safe to run many times and on a database with real orders:
nothing is deleted, prices and stock of existing products are not changed.

    python manage.py load_catalog
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from shop.models import Category, Product, ProductImage
from .catalog_extra import GALLERIES, LOCAL_PHOTOS, MOVES, NEW_CATEGORIES, NEW_PRODUCTS
from .descriptions import DESCRIPTIONS
from .seed_shop import CATEGORIES as BASE_CATEGORIES


class Command(BaseCommand):
    help = "Add new products, categories and photo galleries (does not delete anything)"

    @transaction.atomic
    def handle(self, *args, **opts):
        cats = {}
        for en, ru, kk in BASE_CATEGORIES + NEW_CATEGORIES:   # a missing category is created
            cats[en], _ = Category.objects.get_or_create(name_en=en, defaults={"name_ru": ru, "name_kk": kk})

        moved = 0
        for sku, cat in MOVES.items():
            moved += Product.objects.filter(sku=sku).exclude(category=cats[cat]).update(category=cats[cat])

        created = 0
        galleries = dict(GALLERIES)
        for sku, cat, en, ru, kk, price, stock, brand, photos, d_en, d_ru, d_kk in NEW_PRODUCTS:
            product, is_new = Product.objects.get_or_create(sku=sku, defaults=dict(
                category=cats[cat], name_en=en, name_ru=ru, name_kk=kk,
                price=Decimal(price), stock_quantity=stock, brand=brand, image_url=photos[0],
                description_en=d_en, description_ru=d_ru, description_kk=d_kk,
            ))
            created += is_new
            galleries[sku] = photos

        photos_added = 0
        for product in Product.objects.filter(sku__in=galleries.keys()):
            urls = galleries[product.sku]
            if not product.image_url:
                product.image_url = urls[0]
                product.save(update_fields=["image_url"])
            have = set(product.images.values_list("url", flat=True))
            start = product.images.count()
            for url in urls:
                if url not in have:
                    ProductImage.objects.create(product=product, url=url, position=start)
                    start += 1
                    photos_added += 1

        for sku, path in LOCAL_PHOTOS.items():
            photos_added += Product.objects.filter(sku=sku, image_url="").update(image_url=path)

        filled = 0
        for product in Product.objects.filter(sku__in=DESCRIPTIONS.keys()):
            en, ru, kk = DESCRIPTIONS[product.sku]
            changed = []
            for field, text in (("description_en", en), ("description_ru", ru), ("description_kk", kk)):
                if text and not getattr(product, field).strip():
                    setattr(product, field, text)
                    changed.append(field)
            if changed:
                product.save(update_fields=changed)
                filled += 1

        self.stdout.write(self.style.SUCCESS(
            f"New products: {created}. Moved to a new category: {moved}. Photos added: {photos_added}. "
            f"Descriptions filled: {filled}. Products in shop: {Product.objects.count()}."
        ))
