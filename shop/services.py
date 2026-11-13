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

from . import payments
from .models import (
    Address, CartItem, Category, Notification, Order, OrderItem, Payment, Product, PromoCode,
)


class OutOfStockError(Exception):
    """Raised when a product does not have enough stock."""


class EmptyCartError(Exception):
    """Raised when the customer tries to order an empty cart."""


class CancelNotAllowedError(Exception):
    """Raised when an order can no longer be cancelled (already shipped, delivered or cancelled)."""


INSTALLMENT_MONTHS = (3, 6, 12, 24)


class PaymentMethodError(Exception):
    """Wrong payment options (e.g. installment months)."""


class PromoCodeError(Exception):
    """Raised when a promo code does not exist, expired, is used up or the order is too small."""


class OrderTransitionError(Exception):
    """Raised when fulfillment would skip or reverse an order state."""


@transaction.atomic
def fulfill_order(order: Order, target_status: str) -> Order:
    """Advance fulfillment once; the lock serializes cancellation and shipping."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    transitions = {
        Order.Status.SHIPPED: Order.Status.PAID,
        Order.Status.DELIVERED: Order.Status.SHIPPED,
    }
    payment = Payment.objects.select_for_update().filter(order=order).first()
    cash = payment is not None and payment.method == Payment.Method.CASH
    # cash on delivery: the courier takes the order before it is paid
    allowed = (order.status == transitions.get(target_status)
               or (cash and target_status == Order.Status.SHIPPED and order.status == Order.Status.PENDING))
    if not allowed:
        raise OrderTransitionError("The order cannot move to that status.")
    order.status = target_status
    order.save(update_fields=["status", "updated_at"])
    if cash and target_status == Order.Status.DELIVERED and payment.status == Payment.Status.PENDING:
        payment.status, payment.paid_at = Payment.Status.PAID, timezone.now()     # courier got the money
        payment.save(update_fields=["status", "paid_at"])
    ru = {"shipped": "отправлен", "delivered": "доставлен"}[target_status]
    kk = {"shipped": "жіберілді", "delivered": "жеткізілді"}[target_status]
    Notification.objects.create(
        user=order.user, order=order, link="/orders",
        message=f"Order #{order.pk} is {target_status}.",
        message_ru=f"Заказ №{order.pk} {ru}.",
        message_kk=f"№{order.pk} тапсырыс {kk}.",
    )
    return order


# ---------------------------------------------------------------------
# CHECKOUT - all steps succeed together or all are cancelled (ROLLBACK)
# ---------------------------------------------------------------------
@transaction.atomic
def place_order(user, address: Address, method: str, promo_code: str = "", card: dict | None = None,
                installment_months: int | None = None) -> Order:
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

    # 3. Totals and promo code (the promo row is locked: two orders cannot take its last "use")
    subtotal = sum((products[i.product_id].price * i.quantity for i in cart), Decimal("0"))
    promo = check_promo(promo_code, subtotal, lock=True) if promo_code else None
    discount = discount_for(promo, subtotal) if promo else Decimal("0")
    total = subtotal - discount

    # 4. Payment. Card: ask the (demo) bank now. Wrong card data -> CardInvalid -> nothing saved.
    #    Bank transfer / cash on delivery: the order waits for the money.
    result = None
    if method == Payment.Method.INSTALLMENT and installment_months not in INSTALLMENT_MONTHS:
        raise PaymentMethodError("Choose 3, 6, 12 or 24 months.")
    if method == Payment.Method.CARD and card is not None:
        result = payments.charge(card, total)
    declined = result is not None and not result.approved
    if declined:
        order_status, pay_status = Order.Status.CANCELLED, Payment.Status.FAILED
    elif method in (Payment.Method.CARD, Payment.Method.INSTALLMENT):   # the bank pays the shop at once
        order_status, pay_status = Order.Status.PAID, Payment.Status.PAID
    else:
        order_status, pay_status = Order.Status.PENDING, Payment.Status.PENDING

    # 5. The order (address is copied as text) and its lines with the price at purchase time
    order = Order.objects.create(user=user, shipping_address=address.full_text(), status=order_status,
                                 total_amount=total, discount_amount=discount, promo_code=promo)
    for item in cart:
        product = products[item.product_id]
        OrderItem.objects.create(order=order, product=product,
                                 quantity=item.quantity, unit_price=product.price)
        if not declined:                     # a declined payment does not take goods from the stock
            Product.objects.filter(id=product.id).update(
                stock_quantity=F("stock_quantity") - item.quantity)
    if promo and not declined:
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)

    Payment.objects.create(
        order=order, method=method, amount=total, status=pay_status,
        paid_at=timezone.now() if pay_status == Payment.Status.PAID else None,
        provider_reference=result.reference if result else f"DEMO-{order.pk:06d}",
        card_brand=result.brand if result else "", card_last4=result.last4 if result else "",
        failure_reason=result.reason if declined else "",
        installment_months=installment_months if method == Payment.Method.INSTALLMENT else None,
    )

    # 6. Empty the cart (kept after a declined card, so the customer can try again) and notify
    if not declined:
        CartItem.objects.filter(user=user).delete()
    n = order.pk
    texts = {
        Order.Status.PAID: (f"Order #{n} is paid.", f"Заказ №{n} оплачен.", f"№{n} тапсырыс төленді."),
        Order.Status.CANCELLED: (f"Payment for order #{n} was declined by the bank.",
                                 f"Оплата заказа №{n} отклонена банком.",
                                 f"№{n} тапсырыстың төлемін банк қабылдамады."),
    }
    if method == Payment.Method.INSTALLMENT:
        monthly = (total / installment_months).quantize(Decimal("0.01"))
        texts[Order.Status.PAID] = (
            f"Order #{n} is paid by installment: {installment_months} × ${monthly}, 0% overpayment.",
            f"Заказ №{n} оплачен в рассрочку: {installment_months} × ${monthly}, без переплаты.",
            f"№{n} тапсырыс бөліп төлеумен төленді: {installment_months} × ${monthly}, үстеме жоқ.")
    if method == Payment.Method.QR:
        texts[Order.Status.PENDING] = (f"Order #{n}: scan the QR code in your bank app to pay ${total}.",
                                       f"Заказ №{n}: отсканируйте QR в приложении банка и оплатите ${total}.",
                                       f"№{n} тапсырыс: банк қосымшасында QR сканерлеп, ${total} төлеңіз.")
    elif method == Payment.Method.BANK_TRANSFER:
        texts[Order.Status.PENDING] = (f"Order #{n} is waiting for your bank transfer of ${total}.",
                                       f"Заказ №{n} ждёт банковский перевод на ${total}.",
                                       f"№{n} тапсырыс ${total} банк аударымын күтуде.")
    else:
        texts[Order.Status.PENDING] = (f"Order #{n} is accepted. Pay ${total} to the courier.",
                                       f"Заказ №{n} принят. Оплата ${total} курьеру при получении.",
                                       f"№{n} тапсырыс қабылданды. ${total} курьерге төленеді.")
    en, ru, kk = texts[order_status]
    Notification.objects.create(user=user, order=order, link="/orders",
                                message=en, message_ru=ru, message_kk=kk)
    return order
    # If ANY step above raises an error, Django runs ROLLBACK automatically.


@transaction.atomic
def confirm_payment(order: Order) -> Order:
    """Staff: the bank transfer has arrived -> payment paid, order paid."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    payment = Payment.objects.select_for_update().filter(order=order).first()
    if order.status != Order.Status.PENDING or payment is None or payment.status != Payment.Status.PENDING:
        raise OrderTransitionError("The payment cannot be confirmed.")
    payment.status, payment.paid_at = Payment.Status.PAID, timezone.now()
    payment.save(update_fields=["status", "paid_at"])
    order.status = Order.Status.PAID
    order.save(update_fields=["status", "updated_at"])
    Notification.objects.create(
        user=order.user, order=order, link="/orders",
        message=f"Payment for order #{order.pk} has arrived. Thank you!",
        message_ru=f"Оплата заказа №{order.pk} получена. Спасибо!",
        message_kk=f"№{order.pk} тапсырыстың төлемі түсті. Рақмет!",
    )
    return order


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

    # 4b. The promo code use comes back
    if order.promo_code_id:
        PromoCode.objects.filter(pk=order.promo_code_id, used_count__gt=0).update(
            used_count=F("used_count") - 1)

    # 5. Tell the customer
    refunded = payment is not None and payment.status == Payment.Status.REFUNDED
    sum_text = f" ${order.total_amount}"
    Notification.objects.create(
        user=order.user, order=order, link="/orders",
        message=f"Order #{order.pk} is cancelled." + (f"{sum_text} will be refunded." if refunded else ""),
        message_ru=f"Заказ №{order.pk} отменён." + (f"{sum_text} будут возвращены." if refunded else ""),
        message_kk=f"№{order.pk} тапсырыс тоқтатылды." + (f"{sum_text} қайтарылады." if refunded else ""),
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
# MANAGER REPORTS for a period (staff panel -> Отчёты). Cancelled orders are not counted.
# ---------------------------------------------------------------------
def _sold_items(since=None):
    items = OrderItem.objects.exclude(order__status=Order.Status.CANCELLED)
    return items.filter(order__created_at__gte=since) if since else items


_LINE = ExpressionWrapper(F("quantity") * F("unit_price"),
                          output_field=DecimalField(max_digits=12, decimal_places=2))


def report_summary(since=None) -> dict:
    orders = Order.objects.exclude(status=Order.Status.CANCELLED)
    if since:
        orders = orders.filter(created_at__gte=since)
    totals = orders.aggregate(revenue=Sum("total_amount"), discounts=Sum("discount_amount"),
                              count=Count("id"))
    count = totals["count"] or 0
    revenue = totals["revenue"] or Decimal("0")
    cancelled = Order.objects.filter(status=Order.Status.CANCELLED)
    if since:
        cancelled = cancelled.filter(created_at__gte=since)
    return {
        "orders": count, "revenue": revenue, "discounts": totals["discounts"] or Decimal("0"),
        "avg_order": (revenue / count).quantize(Decimal("0.01")) if count else Decimal("0"),
        "units": _sold_items(since).aggregate(n=Sum("quantity"))["n"] or 0,
        "cancelled": cancelled.count(),
    }


def report_sales_by_category(since=None) -> list:
    """[{category, units, revenue, share%}] - before promo discounts."""
    rows = list(_sold_items(since).values("product__category__id", "product__category__name_ru",
                                          "product__category__name_en")
                .annotate(units=Sum("quantity"), revenue=Sum(_LINE)).order_by("-revenue"))
    total = sum((r["revenue"] for r in rows), Decimal("0"))
    for r in rows:
        r["name"] = r["product__category__name_ru"] or r["product__category__name_en"]
        r["share"] = round(float(r["revenue"] / total * 100), 1) if total else 0
    return rows


def report_best_sellers(since=None, limit=10) -> list:
    return list(_sold_items(since).values("product__id", "product__sku", "product__name_ru",
                                          "product__name_en", "product__stock_quantity")
                .annotate(units=Sum("quantity"), revenue=Sum(_LINE)).order_by("-units", "-revenue")[:limit])


def report_low_stock(threshold=10):
    """Active products with stock below the threshold, emptiest first."""
    return (Product.objects.filter(is_active=True, stock_quantity__lt=threshold)
            .select_related("category").order_by("stock_quantity", "name_en"))


def report_promo_usage(since=None) -> list:
    orders = Order.objects.exclude(status=Order.Status.CANCELLED).filter(promo_code__isnull=False)
    if since:
        orders = orders.filter(created_at__gte=since)
    return list(orders.values("promo_code__code", "promo_code__discount_percent")
                .annotate(orders=Count("id"), discount=Sum("discount_amount"), revenue=Sum("total_amount"))
                .order_by("-orders"))


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


# ---------------------------------------------------------------------
# NOTIFICATIONS - one message to many customers (campaigns like Black Friday)
# ---------------------------------------------------------------------
BLACK_FRIDAY = {
    "en": "Black Friday at Sauda is on 27 November! Get ready for special offers - "
          "check the catalog and put your favourites in the cart.",
    "ru": "Чёрная пятница в Sauda — 27 ноября! Готовьтесь к специальным предложениям: "
          "загляните в каталог и добавьте любимые товары в корзину.",
    "kk": "Sauda-дағы Black Friday — 27 қарашада! Арнайы ұсыныстарға дайын болыңыз: "
          "каталогқа кіріп, ұнаған тауарларды себетке салыңыз.",
}


@transaction.atomic
def broadcast_notification(message_en, message_ru="", message_kk="", link="",
                           kind=Notification.Kind.PROMO, users=None) -> int:
    """Creates one notification for every active customer (or for the given users).
    Returns how many notifications were created."""
    from .models import User
    if users is None:
        users = User.objects.filter(is_active=True, role=User.Role.CUSTOMER)
    rows = [Notification(user=u, kind=kind, message=message_en, message_ru=message_ru,
                         message_kk=message_kk, link=link) for u in users]
    Notification.objects.bulk_create(rows)          # one INSERT for all customers
    return len(rows)


def send_black_friday(users=None) -> int:
    return broadcast_notification(BLACK_FRIDAY["en"], BLACK_FRIDAY["ru"], BLACK_FRIDAY["kk"],
                                  link="/catalog", users=users)


# ---------------------------------------------------------------------
# PROMO CODES
# ---------------------------------------------------------------------
def check_promo(code: str, order_total: Decimal, lock: bool = False) -> PromoCode:
    """Returns the PromoCode or raises PromoCodeError with the reason."""
    code = (code or "").strip().upper()
    qs = PromoCode.objects.select_for_update() if lock else PromoCode.objects
    promo = qs.filter(code=code, is_active=True).first()
    now = timezone.now()
    if promo is None:
        raise PromoCodeError("Promo code not found.")
    if promo.valid_from and now < promo.valid_from:
        raise PromoCodeError("Promo code is not active yet.")
    if promo.valid_until and now > promo.valid_until:
        raise PromoCodeError("Promo code has expired.")
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        raise PromoCodeError("Promo code has been used up.")
    if order_total < promo.min_order_amount:
        raise PromoCodeError(f"Minimum order for this code is ${promo.min_order_amount}.")
    return promo


def discount_for(promo: PromoCode, total: Decimal) -> Decimal:
    return (total * promo.discount_percent / Decimal(100)).quantize(Decimal("0.01"))


def cart_total(user) -> Decimal:
    return sum((i.product.price * i.quantity
                for i in CartItem.objects.filter(user=user).select_related("product")), Decimal("0"))
