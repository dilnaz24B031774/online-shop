"""One immutable review per authenticated account and product."""
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Category, Product, Review, User


class ProductReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("reviewer", "reviewer@example.test", "Shop2026!")
        cls.other = User.objects.create_user("other", "other@example.test", "Shop2026!")
        category = Category.objects.create(name_en="Review products")
        cls.product = Product.objects.create(
            category=category, sku="REVIEW-1", name_en="First product", price="10.00",
        )
        cls.second = Product.objects.create(
            category=category, sku="REVIEW-2", name_en="Second product", price="20.00",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)

    def submit(self, product=None, **data):
        return self.api.post(f"/api/products/{(product or self.product).pk}/reviews/", {
            "rating": 5, "comment": "Very useful", **data,
        }, format="json")

    def test_duplicate_is_rejected_and_original_review_is_preserved(self):
        first = self.submit()
        self.assertEqual(first.status_code, 201)
        duplicate = self.submit(rating=1, comment="Replacement")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["code"], "review_exists")
        review = Review.objects.get(user=self.user, product=self.product)
        self.assertEqual((review.rating, review.comment), (5, "Very useful"))
        self.assertEqual(Review.objects.count(), 1)

    def test_each_account_can_review_each_different_product(self):
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(self.submit(self.second).status_code, 201)
        self.api.force_authenticate(self.other)
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(Review.objects.count(), 3)

    def test_review_ownership_uses_stable_read_only_user_id(self):
        response = self.submit(user_id=self.other.pk, username=self.other.username)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user_id"], self.user.pk)
        self.user.username = "renamed_reviewer"
        self.user.save(update_fields=["username"])
        public = APIClient()
        review = public.get(f"/api/products/{self.product.pk}/").json()["reviews"][0]
        self.assertEqual(review["user_id"], self.user.pk)
        self.assertEqual(review["username"], "renamed_reviewer")
        self.assertEqual(self.submit().json()["code"], "review_exists")

    def test_anonymous_user_cannot_review(self):
        self.api.force_authenticate(None)
        self.assertEqual(self.submit().status_code, 401)
        self.assertFalse(Review.objects.exists())

    def test_rating_must_be_an_integer_between_one_and_five(self):
        for rating in (0, 6, -1, 1.5, "bad"):
            with self.subTest(rating=rating):
                response = self.submit(rating=rating)
                self.assertEqual(response.status_code, 400)
                self.assertIn("rating", response.json())
        self.assertFalse(Review.objects.exists())

    def test_inactive_product_cannot_be_reviewed(self):
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        self.assertEqual(self.submit().status_code, 404)
        self.assertFalse(Review.objects.exists())

    def test_database_rejects_duplicates_even_outside_the_api(self):
        Review.objects.create(user=self.user, product=self.product, rating=5)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(user=self.user, product=self.product, rating=1)
        self.assertEqual(Review.objects.count(), 1)

    def test_duplicate_insert_race_returns_a_friendly_error(self):
        self.submit()
        # Another request committed the review after this request's initial
        # existence check. Exercise the real unique violation and savepoint.
        with patch("shop.api.Review.objects.filter") as reviews:
            reviews.return_value.exists.side_effect = [False, True]
            response = self.submit(rating=1)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "review_exists")
        self.assertEqual(Review.objects.get().rating, 5)
