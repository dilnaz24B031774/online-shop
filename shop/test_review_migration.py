"""The purchase-link migration preserves reviews without inventing proof."""
from datetime import timedelta

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class PurchaseReviewMigrationTests(TransactionTestCase):
    migrate_from = ("shop", "0009_complaint")
    migrate_to = ("shop", "0010_review_order_item")

    def setUp(self):
        super().setUp()
        executor = MigrationExecutor(connection)
        self.latest_targets = executor.loader.graph.leaf_nodes()
        # Restore the normal schema even if historical fixture creation fails.
        self.addCleanup(self.restore_latest)
        executor.migrate([self.migrate_from])
        self.old_apps = executor.loader.project_state([self.migrate_from]).apps
        self.create_historical_data()
        executor = MigrationExecutor(connection)
        executor.migrate([self.migrate_to])
        self.apps = executor.loader.project_state([self.migrate_to]).apps

    def restore_latest(self):
        MigrationExecutor(connection).migrate(self.latest_targets)

    def create_historical_data(self):
        User = self.old_apps.get_model("shop", "User")
        Category = self.old_apps.get_model("shop", "Category")
        Product = self.old_apps.get_model("shop", "Product")
        Review = self.old_apps.get_model("shop", "Review")
        self.reviewed_at = timezone.now() - timedelta(days=10)
        self.user = User.objects.create(username="migration_buyer", email="buyer@migration.test")
        self.other = User.objects.create(username="migration_other", email="other@migration.test")
        category = Category.objects.create(name_en="Migration products")
        self.products = {
            key: Product.objects.create(category=category, sku=f"MIGRATION-{key}", name_en=key, price="10.00")
            for key in ("linked", "unsupported", "created_later", "paid_later")
        }
        before = self.reviewed_at - timedelta(days=2)
        after = self.reviewed_at + timedelta(days=2)
        self.matching_item = self.purchase(self.products["linked"], before, before)
        self.foreign_item = self.purchase(self.products["unsupported"], before, before, user=self.other)
        self.cancelled_item = self.purchase(
            self.products["unsupported"], before, before, order_status="cancelled", payment_status="refunded",
        )
        # The intentionally inconsistent first case verifies the order date
        # independently of paid_at; both dates must precede the review.
        self.created_later_item = self.purchase(self.products["created_later"], after, before)
        self.paid_later_item = self.purchase(self.products["paid_later"], before, after)
        self.review_ids = {}
        self.original_reviews = {}
        for index, (key, product) in enumerate(self.products.items(), start=1):
            review = Review.objects.create(
                user=self.user, product=product, rating=index, comment=f"Original {key} review",
            )
            Review.objects.filter(pk=review.pk).update(created_at=self.reviewed_at)
            self.review_ids[key] = review.pk
            self.original_reviews[review.pk] = {
                "user_id": self.user.pk, "product_id": product.pk, "rating": index,
                "comment": review.comment, "created_at": self.reviewed_at,
            }

    def purchase(self, product, created_at, paid_at, *, user=None, order_status="paid", payment_status="paid", apps=None):
        apps = apps or self.old_apps
        Order = apps.get_model("shop", "Order")
        OrderItem = apps.get_model("shop", "OrderItem")
        Payment = apps.get_model("shop", "Payment")
        order = Order.objects.create(
            user_id=(user or self.user).pk, status=order_status,
            shipping_address="Migration address", total_amount="30.00",
        )
        Order.objects.filter(pk=order.pk).update(created_at=created_at)
        item = OrderItem.objects.create(order=order, product_id=product.pk, quantity=3, unit_price="10.00")
        Payment.objects.create(order=order, method="card", status=payment_status, amount="30.00", paid_at=paid_at)
        return item

    def test_links_only_proven_historical_purchases_and_keeps_repeat_purchase_available(self):
        Review = self.apps.get_model("shop", "Review")
        self.assertEqual(Review.objects.count(), len(self.original_reviews))
        for review_id, original in self.original_reviews.items():
            review = Review.objects.get(pk=review_id)
            self.assertEqual({field: getattr(review, field) for field in original}, original)

        self.assertEqual(Review.objects.get(pk=self.review_ids["linked"]).order_item_id, self.matching_item.pk)
        for key in ("unsupported", "created_later", "paid_later"):
            self.assertIsNone(Review.objects.get(pk=self.review_ids[key]).order_item_id)
        self.assertFalse(Review.objects.filter(order_item_id__in=(
            self.foreign_item.pk, self.cancelled_item.pk, self.created_later_item.pk, self.paid_later_item.pk,
        )).exists())

        # A later purchase of an already reviewed product is a new entitlement.
        # This also proves the previous UNIQUE(user, product) was removed.
        later = self.reviewed_at + timedelta(days=3)
        repeat_item = self.purchase(self.products["linked"], later, later, apps=self.apps)
        Review.objects.create(
            user_id=self.user.pk, product_id=self.products["linked"].pk,
            order_item_id=repeat_item.pk, rating=5, comment="Review after buying again",
        )
        self.assertEqual(Review.objects.filter(user_id=self.user.pk, product_id=self.products["linked"].pk).count(), 2)
        # Unsupported old reviews must not consume the purchase made later.
        Review.objects.create(
            user_id=self.user.pk, product_id=self.products["paid_later"].pk,
            order_item_id=self.paid_later_item.pk, rating=5, comment="Review after actual payment",
        )
        self.assertEqual(Review.objects.count(), len(self.original_reviews) + 2)
