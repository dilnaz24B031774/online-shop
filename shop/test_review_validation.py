"""Model validation protects purchase ownership and immutable review links."""
from io import StringIO

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from .models import Category, Order, OrderItem, Payment, Product, Review, User


class PurchaseReviewValidationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user("model_buyer", "buyer@review.test", "Shop2026!")
        cls.other = User.objects.create_user("model_other", "other@review.test", "Shop2026!")
        category = Category.objects.create(name_en="Review validation products")
        cls.product = Product.objects.create(category=category, sku="REVIEW-MODEL-1", name_en="First", price="10.00")
        cls.second = Product.objects.create(category=category, sku="REVIEW-MODEL-2", name_en="Second", price="10.00")

    def purchase(self, *, user=None, product=None, order_status=Order.Status.PAID,
                 payment_status=Payment.Status.PAID, with_payment=True):
        order = Order.objects.create(
            user=user or self.user, status=order_status, total_amount="10.00", shipping_address="Review address",
        )
        item = OrderItem.objects.create(order=order, product=product or self.product, quantity=1, unit_price="10.00")
        if with_payment:
            Payment.objects.create(
                order=order, method=Payment.Method.CARD, status=payment_status, amount="10.00",
                paid_at=timezone.now() if payment_status == Payment.Status.PAID else None,
            )
        return item

    def review(self, item=None, **values):
        return Review(user=self.user, product=self.product, order_item=item, rating=5, comment="Purchased review", **values)

    def test_new_review_requires_a_purchase(self):
        with self.assertRaises(ValidationError) as error:
            self.review().full_clean()
        self.assertIn("order_item", error.exception.message_dict)

    def test_purchase_must_belong_to_review_author(self):
        with self.assertRaises(ValidationError) as error:
            self.review(self.purchase(user=self.other)).full_clean()
        self.assertIn("user", error.exception.message_dict)

    def test_purchase_product_must_match_review_product(self):
        with self.assertRaises(ValidationError) as error:
            self.review(self.purchase(product=self.second)).full_clean()
        self.assertIn("product", error.exception.message_dict)

    def test_unpaid_cancelled_refunded_and_missing_payments_are_rejected(self):
        cases = (
            (Order.Status.PENDING, Payment.Status.PENDING),
            (Order.Status.CANCELLED, Payment.Status.REFUNDED),
            (Order.Status.PAID, Payment.Status.FAILED),
            (Order.Status.DELIVERED, Payment.Status.PENDING),
            (Order.Status.SHIPPED, Payment.Status.PENDING),
        )
        for order_status, payment_status in cases:
            with self.subTest(order_status=order_status, payment_status=payment_status):
                item = self.purchase(order_status=order_status, payment_status=payment_status)
                with self.assertRaises(ValidationError) as error:
                    self.review(item).full_clean()
                self.assertIn("order_item", error.exception.message_dict)
        with self.assertRaises(ValidationError) as error:
            self.review(self.purchase(with_payment=False)).full_clean()
        self.assertIn("order_item", error.exception.message_dict)

    def test_paid_shipped_and_delivered_purchases_allow_review(self):
        for status in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED):
            with self.subTest(status=status):
                review = self.review(self.purchase(order_status=status))
                review.full_clean()
                review.save()
        self.assertEqual(Review.objects.count(), 3)

    def test_published_review_author_product_and_purchase_are_immutable(self):
        item = self.purchase()
        review = self.review(item)
        review.full_clean()
        review.save()
        another_item = self.purchase()
        for field, value in (("user", self.other), ("product", self.second), ("order_item", another_item), ("order_item", None)):
            with self.subTest(field=field, value=value):
                changed = Review.objects.get(pk=review.pk)
                setattr(changed, field, value)
                with self.assertRaises(ValidationError) as error:
                    changed.full_clean()
                self.assertIn("cannot be changed", str(error.exception))
        review.refresh_from_db()
        self.assertEqual((review.user_id, review.product_id, review.order_item_id), (self.user.pk, self.product.pk, item.pk))

    def test_existing_review_can_be_moderated_after_refund(self):
        item = self.purchase()
        review = self.review(item)
        review.full_clean()
        review.save()
        Order.objects.filter(pk=item.order_id).update(status=Order.Status.CANCELLED)
        Payment.objects.filter(order_id=item.order_id).update(status=Payment.Status.REFUNDED)
        review = Review.objects.get(pk=review.pk)
        review.comment = "Moderated after the refund"
        review.rating = 4
        review.full_clean()
        review.save(update_fields=["comment", "rating"])
        review.refresh_from_db()
        self.assertEqual((review.comment, review.rating, review.order_item_id), ("Moderated after the refund", 4, item.pk))

    def test_preserved_legacy_review_can_be_moderated_without_inventing_purchase(self):
        review = Review.objects.create(user=self.user, product=self.product, rating=4, comment="Legacy review")
        review.comment = "Moderated legacy review"
        review.full_clean()
        review.save(update_fields=["comment"])
        review.refresh_from_db()
        self.assertIsNone(review.order_item_id)
        self.assertEqual(review.comment, "Moderated legacy review")


class SeedPurchaseReviewIntegrityTests(TestCase):
    def test_seeded_reviews_are_backed_by_distinct_owned_paid_purchases(self):
        call_command("seed_shop", stdout=StringIO())
        reviews = list(Review.objects.select_related("order_item__order__payment"))
        self.assertGreater(len(reviews), 0)
        self.assertEqual(len({review.order_item_id for review in reviews}), len(reviews))
        for review in reviews:
            with self.subTest(review_id=review.pk):
                self.assertIsNotNone(review.order_item_id)
                purchase = review.order_item
                self.assertEqual(purchase.order.user_id, review.user_id)
                self.assertEqual(purchase.product_id, review.product_id)
                self.assertIn(purchase.order.status, (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED))
                self.assertEqual(purchase.order.payment.status, Payment.Status.PAID)
                self.assertLessEqual(purchase.order.payment.paid_at, review.created_at)
