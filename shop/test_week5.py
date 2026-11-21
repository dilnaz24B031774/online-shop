import os
import shutil
import tempfile
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from . import backups
from .models import Category, City, Order, OrderItem, Payment, Product, Review, ReviewPhoto, User

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPG = b"\xff\xd8\xff\xe0" + b"\x00" * 64
WEBP = b"RIFF\x00\x00\x00\x00WEBP" + b"\x00" * 64


def upload(name, data, kind="image/png"):
    return SimpleUploadedFile(name, data, content_type=kind)


class CityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        self.api = APIClient()

    def test_cities_are_filled_by_migration_almaty_first(self):
        data = self.api.get("/api/cities/").json()
        self.assertGreaterEqual(len(data), 18)
        self.assertEqual(data[0]["name_en"], "Almaty")

    def test_user_saves_and_clears_city(self):
        self.api.force_authenticate(self.user)
        astana = City.objects.get(name_en="Astana")
        r = self.api.patch("/api/me/", {"city_id": astana.id}, format="json")
        self.assertEqual(r.json()["city"]["name_ru"], "Астана")
        self.user.refresh_from_db()
        self.assertEqual(self.user.city, astana)
        self.assertIsNone(self.api.patch("/api/me/", {"city_id": None}, format="json").json()["city"])

    def test_inactive_city_cannot_be_chosen(self):
        self.api.force_authenticate(self.user)
        c = City.objects.create(name_en="Ghost", name_ru="Призрак", name_kk="Елес", is_active=False)
        self.assertEqual(self.api.patch("/api/me/", {"city_id": c.id}, format="json").status_code, 400)

    def test_delivery_days_rule_in_database(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            City.objects.create(name_en="Bad", name_ru="Плохо", name_kk="Жаман", delivery_days_min=5, delivery_days_max=2)


class ReviewPhotoTests(TestCase):
    def setUp(self):
        self.media = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media)
        self.override.enable()
        self.user = User.objects.create_user("aigerim", "a@ex.com", "Shop2026!")
        cat = Category.objects.create(name_en="Books")
        self.product = Product.objects.create(sku="BK-1", category=cat, name_en="Book", price=Decimal("10"), stock_quantity=5)
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.url = f"/api/products/{self.product.id}/reviews/"
        # a review needs a paid purchase of the product (rule from the reviews part)
        order = Order.objects.create(user=self.user, status="delivered", shipping_address="Almaty", total_amount=Decimal("10"))
        OrderItem.objects.create(order=order, product=self.product, quantity=1, unit_price=Decimal("10"))
        Payment.objects.create(order=order, method="card", status="paid", amount=Decimal("10"), paid_at=timezone.now())

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media, ignore_errors=True)

    def test_review_with_three_photos(self):
        r = self.api.post(self.url, {"rating": 5, "comment": "Nice", "photos": [
            upload("a.png", PNG), upload("b.jpg", JPG, "image/jpeg"), upload("c.webp", WEBP, "image/webp")]}, format="multipart")
        self.assertEqual(r.status_code, 201, r.content)
        self.assertEqual(len(r.json()["photos"]), 3)
        self.assertTrue(r.json()["photos"][0].startswith("/media/reviews/"))
        detail = APIClient().get(f"/api/products/{self.product.id}/").json()
        self.assertEqual(len(detail["reviews"][0]["photos"]), 3)

    def test_fake_image_is_rejected_and_nothing_saved(self):
        r = self.api.post(self.url, {"rating": 4, "photos": [upload("virus.png", b"MZ\x90\x00 not an image")]}, format="multipart")
        self.assertEqual(r.status_code, 400)
        self.assertFalse(Review.objects.exists())

    def test_more_than_three_photos_rejected(self):
        files = [upload(f"{n}.png", PNG) for n in range(4)]
        self.assertEqual(self.api.post(self.url, {"rating": 4, "photos": files}, format="multipart").status_code, 400)

    @override_settings(REVIEW_PHOTO_MAX_MB=0)
    def test_too_big_photo_rejected(self):
        r = self.api.post(self.url, {"rating": 4, "photos": [upload("a.png", PNG)]}, format="multipart")
        self.assertEqual(r.status_code, 400)

    def test_review_without_photos_still_works_as_json(self):
        r = self.api.post(self.url, {"rating": 3, "comment": "ok"}, format="json")
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["photos"], [])

    def test_database_allows_only_positions_0_1_2(self):
        review = Review.objects.create(user=self.user, product=self.product, rating=5,
                                       order_item=OrderItem.objects.get(order__user=self.user))
        with self.assertRaises(IntegrityError), transaction.atomic():
            ReviewPhoto.objects.create(review=review, image="reviews/x.png", position=3)


class BackupTests(TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.override = override_settings(BACKUP_DIR=self.dir)
        self.override.enable()

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_json_backup_and_keep_limit(self):
        for _ in range(3):
            backups.create_backup(keep=2, force_json=True)
        files = backups.list_backups()
        self.assertLessEqual(len(files), 2)
        self.assertTrue(files[0].name.endswith(".json"))

    def test_get_backup_blocks_other_paths(self):
        self.assertIsNone(backups.get_backup("../config/settings.py"))
        self.assertIsNone(backups.get_backup("sauda_bad.sql"))

    def test_staff_page_only_for_admin(self):
        admin = User.objects.create_user("boss", "b@ex.com", "Shop2026!", role="admin", is_staff=True, is_superuser=True)
        manager = User.objects.create_user("man", "m@ex.com", "Shop2026!", role="manager", is_staff=True)
        c = self.client
        c.force_login(manager)
        self.assertEqual(c.get("/staff/backups/").status_code, 403)
        c.force_login(admin)
        self.assertEqual(c.get("/staff/backups/").status_code, 200)
        path = backups.create_backup(force_json=True)
        r = c.get(f"/staff/backups/{path.name}/")
        self.assertEqual(r.status_code, 200)
        self.assertIn("attachment", r["Content-Disposition"])


class NewCategoriesTests(TestCase):
    def test_load_catalog_creates_new_categories_and_moves(self):
        call_command("load_catalog", stdout=open(os.devnull, "w"))
        for name in ("Watches", "Jewelry", "Furniture", "Phone accessories", "Auto & Moto"):
            self.assertTrue(Category.objects.get(name_en=name).products.exists(), name)
