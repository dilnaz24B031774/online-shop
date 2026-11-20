"""A paid order line grants one review, regardless of its quantity."""
from rest_framework import serializers

from .models import Order, OrderItem, Payment


PURCHASED_ORDER_STATUSES = (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)


class ReviewPurchaseSerializer(serializers.Serializer):
    order_item_id = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)

    def validate_order_item_id(self, value):
        if isinstance(self.initial_data.get("order_item_id"), bool):
            raise serializers.ValidationError("Choose a purchase from your orders.")
        return value


def eligible_purchases(user, product):
    return OrderItem.objects.filter(
        order__user=user,
        product=product,
        order__status__in=PURCHASED_ORDER_STATUSES,
        order__payment__status=Payment.Status.PAID,
    )


def review_eligibility(user, product):
    if not user.is_authenticated:
        return {
            "can_review": False, "remaining_purchases": 0,
            "reason": "login_required", "purchases": [],
        }
    purchases = eligible_purchases(user, product)
    remaining = list(purchases.filter(review__isnull=True).select_related("order").order_by("order__created_at", "pk"))
    return {
        "can_review": bool(remaining),
        "remaining_purchases": len(remaining),
        "reason": None if remaining else ("review_exists" if purchases.exists() else "purchase_required"),
        "purchases": [
            {"order_item_id": item.pk, "order_id": item.order_id, "purchased_at": item.order.created_at.isoformat()}
            for item in remaining
        ],
    }
