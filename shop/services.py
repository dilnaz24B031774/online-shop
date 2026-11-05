"""
Database operations the rest of the app uses:
  - place_order : checkout as ONE transaction (no overselling)
  - search      : search across products, categories and orders
  - reports     : best sellers, low stock, sales by category
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Q, Sum, F, Count, Avg, DecimalField, ExpressionWrapper
from django.utils import timezone

from .models import (
    Address, CartItem, Category, Notification, Order, OrderItem, Payment, Product,
)


class OutOfStockError(Exception):
    """Raised when a product does not have enough stock."""


class EmptyCartError(Exception):
    """Raised when the customer tries to order an empty cart."""


class CancelNotAllowedError(Exception):
    """Raised when an order can no longer be cancelled (already shipped, delivered or cancelled)."""


# ---------------------------------------------------------------------
# CHECKOUT - all steps succeed together or all are cancelled (ROLLBACK)
# ---------------------------------------------------------------------
@transaction.atomic
def place_order(user, address: Address, method: str) -> Order:
    cart = list(CartItem.objects.filter(user=user).select_related("product"))
    if not cart:
        raise EmptyCartError("The cart is empty.")

    # 1. Lock the product rows: a second customer must WAIT until we finish.
    #    This stops two people from buying the last item at the same moment.
    product_ids = [item.product_id for item in cart]
    products = {
        p.id: p for p in Product.objects.select_for_update().filter(id__in=product_ids)
    }

    # 2. Check stock for every product
    for item in cart:
        product = products[item.product_id]
        if not product.is_active or product.stock_quantity < item.quantity:
            raise OutOfStockError(f"Not enough stock for {product.name_en}.")

    # 3. Create the order (address is copied as text)
    order = Order.objects.create(user=user, shipping_address=address.full_text())

    # 4. Order lines with the price at purchase time + reduce stock
    total = Decimal("0")
    for item in cart:
        product = products[item.product_id]
        OrderItem.objects.create(
            order=order, product=product,
            quantity=item.quantity, unit_price=product.price,
        )
        Product.objects.filter(id=product.id).update(
            stock_quantity=F("stock_quantity") - item.quantity
        )
        total += product.price * item.quantity

    order.total_amount = total
    order.status = Order.Status.PAID
    order.save(update_fields=["total_amount", "status"])

    # 5. Payment (in a real system: the payment provider returns a reference)
    Payment.objects.create(
        order=order, method=method, amount=total,
        status=Payment.Status.PAID, paid_at=timezone.now(),
        provider_reference=f"DEMO-{order.pk:06d}",
    )

    # 6. Empty the cart and notify the customer
    CartItem.objects.filter(user=user).delete()
    Notification.objects.create(user=user, order=order, message=f"Order #{order.pk} is paid.")
    return order
    # If ANY step above raises an error, Django runs ROLLBACK automatically.


# ---------------------------------------------------------------------
# CANCEL + REFUND - one transaction: order, stock, payment, notification
# ---------------------------------------------------------------------
CUSTOMER_CAN_CANCEL = (Order.Status.PENDING, Order.Status.PAID)
STAFF_CAN_CANCEL = (Order.Status.PENDING, Order.Status.PAID, Order.Status.SHIPPED)


@transaction.atomic
def cancel_order(order: Order, by_staff: bool = False) -> Order:
    # 1. Lock the order row: it cannot be cancelled twice at the same time
    order = Order.objects.select_for_update().get(pk=order.pk)
    allowed = STAFF_CAN_CANCEL if by_staff else CUSTOMER_CAN_CANCEL
    if order.status not in allowed:
        raise CancelNotAllowedError(f"Order #{order.pk} is {order.status} and cannot be cancelled.")

    # 2. Return every product to the stock
    for item in order.items.select_for_update():
        Product.objects.filter(id=item.product_id).update(
            stock_quantity=F("stock_quantity") + item.quantity
        )

    # 3. Order -> cancelled
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    # 4. Payment -> refunded (or failed if it was never paid)
    payment = Payment.objects.filter(order=order).first()
    if payment:
        payment.status = (Payment.Status.REFUNDED if payment.status == Payment.Status.PAID
                          else Payment.Status.FAILED)
        payment.save(update_fields=["status"])

    # 5. Tell the customer
    refunded = payment is not None and payment.status == Payment.Status.REFUNDED
    Notification.objects.create(
        user=order.user, order=order,
        message=(f"Order #{order.pk} is cancelled. ${order.total_amount} will be refunded."
                 if refunded else f"Order #{order.pk} is cancelled."),
    )
    return order
    # If any step fails, ROLLBACK: the stock, order and payment stay as they were.


# ---------------------------------------------------------------------
# SEARCH - 3 entity types, all three languages
# ---------------------------------------------------------------------
def search(text: str, user=None) -> dict:
    text = (text or "").strip()
    if not text:
        return {"products": [], "categories": [], "orders": []}

    name_match = Q(name_en__icontains=text) | Q(name_ru__icontains=text) | Q(name_kk__icontains=text)

    products = (
        Product.objects.filter(is_active=True)
        .filter(name_match | Q(sku__icontains=text) | Q(description_en__icontains=text)
                | Q(description_ru__icontains=text))
        .select_related("category")[:20]
    )
    categories = Category.objects.filter(is_active=True).filter(name_match)[:10]

    # Orders: a customer sees only own orders, staff sees all
    orders = Order.objects.none()
    if user is not None:
        order_q = Q(shipping_address__icontains=text) | Q(user__username__icontains=text)
        if text.isdigit():
            order_q |= Q(pk=int(text))
        orders = Order.objects.filter(order_q)
        if user.role == "customer":
            orders = orders.filter(user=user)
        orders = orders[:10]

    return {"products": list(products), "categories": list(categories), "orders": list(orders)}


# ---------------------------------------------------------------------
# REPORTS for the manager / admin panel
# ---------------------------------------------------------------------
_REVENUE = ExpressionWrapper(
    F("order_items__quantity") * F("order_items__unit_price"),
    output_field=DecimalField(max_digits=12, decimal_places=2),
)


def best_sellers(limit=5):
    """Top products by units sold (cancelled orders are ignored)."""
    not_cancelled = ~Q(order_items__order__status=Order.Status.CANCELLED)
    return (
        Product.objects
        .annotate(
            units_sold=Sum("order_items__quantity", filter=not_cancelled),
            revenue=Sum(_REVENUE, filter=not_cancelled),
        )
        .filter(units_sold__gt=0)
        .order_by("-units_sold")[:limit]
    )


def low_stock(threshold=10):
    return Product.objects.filter(is_active=True, stock_quantity__lt=threshold).order_by("stock_quantity")


def sales_by_category():
    not_cancelled = ~Q(products__order_items__order__status=Order.Status.CANCELLED)
    return (
        Category.objects
        .annotate(
            units_sold=Sum("products__order_items__quantity", filter=not_cancelled),
            revenue=Sum(
                F("products__order_items__quantity") * F("products__order_items__unit_price"),
                filter=not_cancelled,
                output_field=DecimalField(max_digits=12, decimal_places=2),
            ),
        )
        .order_by(F("revenue").desc(nulls_last=True))
    )


def product_ratings():
    return Product.objects.annotate(
        avg_rating=Avg("reviews__rating"), review_count=Count("reviews")
    ).filter(review_count__gt=0).order_by("-avg_rating")


# ---------------------------------------------------------------------
# REGISTRATION - check password strength, then save only the hash
# (the backend registration API calls this function)
# ---------------------------------------------------------------------
def register_customer(username: str, email: str, password: str, **extra):
    """
    Raises django.core.exceptions.ValidationError with all problems
    if the password is weak. Nothing is saved in that case.
    """
    from django.contrib.auth.password_validation import validate_password
    from .models import User

    candidate = User(username=username, email=email, role=User.Role.CUSTOMER, **extra)
    validate_password(password, user=candidate)   # 1. strength rules
    candidate.set_password(password)              # 2. hash (pbkdf2_sha256)
    candidate.save()                              # 3. only the hash goes to the database
    return candidate
