import os
import tempfile
from decimal import Decimal
from pathlib import Path

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from config.settings import load_env_file
from shop.models import Category, Product, ProductImage


def run(cmd):
    call_command(cmd, stdout=open(os.devnull, "w"))


class LoadCatalogTests(TestCase):
    def test_adds_products_and_can_run_twice(self):
        run("load_catalog")
        count, photos = Product.objects.count(), ProductImage.objects.count()
        self.assertGreaterEqual(count, 50)
        self.assertTrue(Category.objects.filter(name_en="Kitchen").exists())
        run("load_catalog")
        self.assertEqual(Product.objects.count(), count)
        self.assertEqual(ProductImage.objects.count(), photos)

    def test_keeps_price_and_stock_of_existing_product(self):
        home = Category.objects.create(name_en="Home")
        Product.objects.create(sku="KT-WOK", category=home, name_en="Old wok", price=Decimal("5"), stock_quantity=1)
        run("load_catalog")
        wok = Product.objects.get(sku="KT-WOK")
        self.assertEqual((wok.price, wok.stock_quantity, wok.name_en), (Decimal("5.00"), 1, "Old wok"))
        self.assertTrue(wok.images.exists())

    def test_every_new_product_has_three_languages(self):
        run("load_catalog")
        for p in Product.objects.all():
            self.assertTrue(p.name_ru and p.name_kk and p.description_ru and p.description_kk, p.sku)

    def test_gallery_in_product_api_main_photo_first(self):
        run("load_catalog")
        p = Product.objects.get(sku="EL-MATEX")
        data = APIClient().get(f"/api/products/{p.id}/").json()
        self.assertEqual(data["images"][0], p.image_url)
        self.assertEqual(len(data["images"]), len(set(data["images"])))
        self.assertGreater(len(data["images"]), 1)

    def test_same_photo_twice_is_blocked_by_database(self):
        run("load_catalog")
        img = ProductImage.objects.first()
        with self.assertRaises(IntegrityError), transaction.atomic():
            ProductImage.objects.create(product=img.product, url=img.url, position=99)


class EnvFileTests(TestCase):
    def test_reads_values_and_terminal_wins(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / ".env"
            f.write_text('# comment\nSAUDA_T1=abc\nexport SAUDA_T2="x y"\nPOSTGRES_DB=from_file\n', encoding="utf-8")
            os.environ["POSTGRES_DB_BACKUP"] = os.environ.get("POSTGRES_DB", "")
            load_env_file(f)
            self.assertEqual(os.environ["SAUDA_T1"], "abc")
            self.assertEqual(os.environ["SAUDA_T2"], "x y")
            self.assertNotEqual(os.environ.get("POSTGRES_DB"), "from_file")
            for k in ("SAUDA_T1", "SAUDA_T2", "POSTGRES_DB_BACKUP"):
                os.environ.pop(k, None)
