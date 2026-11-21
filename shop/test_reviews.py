"""One paid order line grants one review; a later purchase grants another."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from django.db import IntegrityError, close_old_connections, transaction
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Category, Order, OrderItem, Payment, Product, Review, User
from .services import cancel_order, fulfill_order


def make_purchase(user, product, *, quantity=1, order_status=Order.Status.PAID,
                  payment_status=Payment.Status.PAID):
    amount = product.price * quantity
    order = Order.objects.create(user=user, shipping_address="Almaty", status=order_status, total_amount=amount)
    item = OrderItem.objects.create(order=order, product=product, quantity=quantity, unit_price=product.price)
    Payment.objects.create(
        order=order, method=Payment.Method.CARD, amount=amount, status=payment_status,
        paid_at=timezone.now() if payment_status == Payment.Status.PAID else None,
    )
    return item


class ProductReviewTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("reviewer", "reviewer@example.test", "Shop2026!")
        cls.other = User.objects.create_user("other", "other@example.test", "Shop2026!")
        category = Category.objects.create(name_en="Review products")
        cls.product = Product.objects.create(category=category, sku="REVIEW-1", name_en="First product", price="10.00")
        cls.second = Product.objects.create(category=category, sku="REVIEW-2", name_en="Second product", price="20.00")

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.user)
        self.product.refresh_from_db()
        self.second.refresh_from_db()

    def submit(self, product=None, **data):
        return self.api.post(f"/api/products/{(product or self.product).pk}/reviews/", {
            "rating": 5, "comment": "Very useful", **data,
        }, format="json")

    def eligibility(self, client=None):
        return (client or self.api).get(f"/api/products/{self.product.pk}/").json()["review_eligibility"]

    def test_review_requires_a_purchase_of_this_product(self):
        make_purchase(self.user, self.second)
        make_purchase(self.other, self.product)
        response = self.submit()
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], "purchase_required")
        self.assertFalse(Review.objects.exists())
        self.assertEqual(self.eligibility(), {
            "can_review": False, "remaining_purchases": 0, "reason": "purchase_required", "purchases": [],
        })

    def test_duplicate_for_one_purchase_is_rejected_without_overwriting_review(self):
        item = make_purchase(self.user, self.product)
        first = self.submit(order_item_id=item.pk)
        self.assertEqual(first.status_code, 201)
        duplicate = self.submit(order_item_id=item.pk, rating=1, comment="Replacement")
        self.assertEqual(duplicate.status_code, 400)
        self.assertEqual(duplicate.json()["code"], "review_exists")
        review = Review.objects.get(order_item=item)
        self.assertEqual((review.user_id, review.product_id, review.rating, review.comment),
                         (self.user.pk, self.product.pk, 5, "Very useful"))
        self.assertEqual(Review.objects.count(), 1)
        self.assertEqual(self.eligibility()["reason"], "review_exists")

    def test_another_purchase_of_same_product_grants_another_review(self):
        first = make_purchase(self.user, self.product)
        second = make_purchase(self.user, self.product)
        self.assertEqual(self.eligibility()["remaining_purchases"], 2)
        self.assertEqual(self.submit(order_item_id=first.pk).status_code, 201)
        self.assertEqual(self.eligibility()["remaining_purchases"], 1)
        self.assertEqual(self.submit(order_item_id=second.pk, rating=3).status_code, 201)
        self.assertEqual(self.eligibility()["remaining_purchases"], 0)
        self.assertEqual(self.submit().json()["code"], "review_exists")
        self.assertEqual(Review.objects.filter(user=self.user, product=self.product).count(), 2)

    def test_quantity_in_one_order_does_not_grant_extra_reviews(self):
        item = make_purchase(self.user, self.product, quantity=5)
        self.assertEqual(self.eligibility()["remaining_purchases"], 1)
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 201)
        self.assertEqual(self.submit().status_code, 400)
        self.assertEqual(Review.objects.count(), 1)

    def test_api_without_selected_purchase_consumes_oldest_available_purchase(self):
        first = make_purchase(self.user, self.product)
        second = make_purchase(self.user, self.product)
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(Review.objects.get().order_item_id, first.pk)
        self.assertEqual(self.submit().status_code, 201)
        self.assertEqual(set(Review.objects.values_list("order_item_id", flat=True)), {first.pk, second.pk})

    def test_explicit_purchase_must_belong_to_current_user_and_product(self):
        theirs = make_purchase(self.other, self.product)
        wrong_product = make_purchase(self.user, self.second)
        mine = make_purchase(self.user, self.product)
        for item_id in (theirs.pk, wrong_product.pk, 999999):
            response = self.submit(order_item_id=item_id)
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json()["code"], "purchase_required")
        self.assertFalse(Review.objects.exists())
        self.assertEqual(self.submit(order_item_id=mine.pk).status_code, 201)

    def test_malformed_purchase_ids_are_rejected_cleanly(self):
        make_purchase(self.user, self.product)
        for value in (0, -1, True, None, "bad", 1.5, 9223372036854775808):
            with self.subTest(value=value):
                response = self.submit(order_item_id=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("order_item_id", response.json())
        self.assertFalse(Review.objects.exists())

    def test_only_paid_and_non_cancelled_orders_grant_reviews(self):
        rejected = (
            (Order.Status.PENDING, Payment.Status.PENDING),
            (Order.Status.PENDING, Payment.Status.PAID),
            (Order.Status.PAID, Payment.Status.PENDING),
            (Order.Status.SHIPPED, Payment.Status.PENDING),
            (Order.Status.DELIVERED, Payment.Status.PENDING),
            (Order.Status.CANCELLED, Payment.Status.PAID),
            (Order.Status.CANCELLED, Payment.Status.REFUNDED),
            (Order.Status.PAID, Payment.Status.FAILED),
            (Order.Status.PAID, Payment.Status.REFUNDED),
        )
        for order_status, payment_status in rejected:
            with self.subTest(order_status=order_status, payment_status=payment_status):
                item = make_purchase(self.user, self.product, order_status=order_status, payment_status=payment_status)
                self.assertEqual(self.submit(order_item_id=item.pk).status_code, 403)
        self.assertEqual(self.eligibility()["remaining_purchases"], 0)
        self.assertFalse(Review.objects.exists())
        for order_status in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED):
            item = make_purchase(self.user, self.product, order_status=order_status)
            self.assertEqual(self.submit(order_item_id=item.pk).status_code, 201)

    def test_cancelled_paid_purchase_cannot_be_reviewed(self):
        item = make_purchase(self.user, self.product)
        self.assertTrue(self.eligibility()["can_review"])
        cancel_order(item.order)
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 403)
        self.assertEqual(self.eligibility()["reason"], "purchase_required")

    def test_cash_on_delivery_grants_review_only_after_courier_collects_payment(self):
        item = make_purchase(self.user, self.product, order_status=Order.Status.PENDING,
                             payment_status=Payment.Status.PENDING)
        Payment.objects.filter(order=item.order).update(method=Payment.Method.CASH)
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 403)
        fulfill_order(item.order, Order.Status.SHIPPED)
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 403)
        fulfill_order(item.order, Order.Status.DELIVERED)
        self.assertTrue(self.eligibility()["can_review"])
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 201)

    def test_review_ownership_is_read_only_and_purchase_ids_are_not_public(self):
        item = make_purchase(self.user, self.product)
        response = self.submit(order_item_id=item.pk, user_id=self.other.pk, username=self.other.username)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.json()["user_id"], self.user.pk)
        self.assertNotIn("order_item_id", response.json())
        self.assertNotIn("order_id", response.json())
        self.user.username = "renamed_reviewer"
        self.user.save(update_fields=["username"])
        detail = APIClient().get(f"/api/products/{self.product.pk}/")
        review = detail.json()["reviews"][0]
        self.assertEqual(review["user_id"], self.user.pk)
        self.assertEqual(review["username"], "renamed_reviewer")
        self.assertNotIn("order_item_id", review)
        self.assertNotIn("order_id", review)
        self.assertEqual(detail["Cache-Control"], "private, no-store")
        self.assertEqual(detail.json()["review_eligibility"]["purchases"], [])

    def test_eligibility_contains_only_current_users_available_purchases(self):
        mine = make_purchase(self.user, self.product)
        reviewed = make_purchase(self.user, self.product)
        theirs = make_purchase(self.other, self.product)
        Review.objects.create(user=self.user, product=self.product, rating=4, order_item=reviewed)
        data = self.eligibility()
        self.assertTrue(data["can_review"])
        self.assertIsNone(data["reason"])
        self.assertEqual(data["remaining_purchases"], 1)
        self.assertEqual([item["order_item_id"] for item in data["purchases"]], [mine.pk])
        self.assertEqual(data["purchases"][0]["order_id"], mine.order_id)
        self.api.force_authenticate(self.other)
        self.assertEqual([item["order_item_id"] for item in self.eligibility()["purchases"]], [theirs.pk])

    def test_legacy_unlinked_review_does_not_consume_a_later_purchase(self):
        Review.objects.create(user=self.user, product=self.product, rating=5)
        item = make_purchase(self.user, self.product)
        self.assertEqual(self.eligibility()["remaining_purchases"], 1)
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 201)
        self.assertEqual(Review.objects.count(), 2)

    def test_anonymous_user_cannot_review_and_sees_no_purchases(self):
        make_purchase(self.user, self.product)
        self.api.force_authenticate(None)
        self.assertEqual(self.submit().status_code, 401)
        self.assertFalse(Review.objects.exists())
        self.assertEqual(self.eligibility(), {
            "can_review": False, "remaining_purchases": 0, "reason": "login_required", "purchases": [],
        })

    def test_rating_must_be_an_integer_between_one_and_five(self):
        make_purchase(self.user, self.product)
        for rating in (0, 6, -1, 1.5, "bad"):
            with self.subTest(rating=rating):
                response = self.submit(rating=rating)
                self.assertEqual(response.status_code, 400)
                self.assertIn("rating", response.json())
        self.assertFalse(Review.objects.exists())

    def test_inactive_product_cannot_be_reviewed(self):
        item = make_purchase(self.user, self.product)
        self.product.is_active = False
        self.product.save(update_fields=["is_active"])
        self.assertEqual(self.submit(order_item_id=item.pk).status_code, 404)
        self.assertFalse(Review.objects.exists())

    def test_database_rejects_duplicate_purchase_even_outside_api(self):
        item = make_purchase(self.user, self.product)
        Review.objects.create(user=self.user, product=self.product, rating=5, order_item=item)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Review.objects.create(user=self.user, product=self.product, rating=1, order_item=item)
        self.assertEqual(Review.objects.count(), 1)

    def test_database_race_returns_a_friendly_error(self):
        item = make_purchase(self.user, self.product)
        Review.objects.create(user=self.user, product=self.product, rating=5, order_item=item)
        with patch("shop.api.Review.objects.filter") as reviews:
            reviews.return_value.exists.side_effect = [False, True]
            response = self.submit(order_item_id=item.pk)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "review_exists")
        self.assertEqual(Review.objects.get().rating, 5)


class ConcurrentPurchaseReviewTests(TransactionTestCase):
    @skipUnlessDBFeature("has_select_for_update")
    def test_simultaneous_requests_for_same_purchase_create_only_one_review(self):
        user = User.objects.create_user("concurrent_reviewer", "concurrent-reviewer@example.test", "Shop2026!")
        category = Category.objects.create(name_en="Concurrent review products")
        product = Product.objects.create(category=category, sku="CONCURRENT-REVIEW", name_en="Product", price="10.00")
        product.refresh_from_db()
        item = make_purchase(user, product)
        barrier = Barrier(2)

        def submit(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=user.pk))
                barrier.wait(timeout=10)
                return client.post(f"/api/products/{product.pk}/reviews/", {
                    "rating": 5, "order_item_id": item.pk,
                }, format="json").status_code
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sorted(pool.map(submit, (1, 2))), [201, 400])
        self.assertEqual(Review.objects.filter(order_item=item).count(), 1)
