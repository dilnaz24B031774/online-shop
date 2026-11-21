"""
Database operations the rest of the app uses:
  - place_order : checkout as ONE transaction (no overselling)
  - search      : search across products, categories and orders
  - reports     : best sellers, low stock, sales by category
"""
import re
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.db.models import Q, Sum, F, Count, Avg, DecimalField, ExpressionWrapper
from django.utils import timezone

from . import payments
from .models import (
    Address, CartItem, Category, Notification, Order, OrderItem, Payment, Product, PromoCode,
    PromoRedemption, QrPayment, Refund, SavedCard, StockSubscription,
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
    """Raised when a promo code does not exist, expired, is used up or the order is too small.
    `code` is a short reason the website translates (not_found, not_active, expired, used_up,
    min_order, already_used)."""

    def __init__(self, message, code="invalid"):
        super().__init__(message)
        self.code = code


class PaymentExpiredError(Exception):
    """The time to pay (QR / bank transfer) is over."""


class RefundError(Exception):
    """The refund is not possible (order not paid, too many items ...)."""


class StockSubscriptionError(Exception):
    """The product is in stock, so there is nothing to wait for."""


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
                installment_months: int | None = None, saved_card_id: int | None = None,
                cvc: str = "", save_card: bool = False) -> Order:
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
    promo = check_promo(promo_code, subtotal, lock=True, user=user) if promo_code else None
    discount = discount_for(promo, subtotal) if promo else Decimal("0")
    total = subtotal - discount

    # 4. Payment. Card: ask the (demo) bank now. Wrong card data -> CardInvalid -> nothing saved.
    #    Bank transfer / cash on delivery: the order waits for the money.
    result = None
    saved = None
    if method == Payment.Method.INSTALLMENT and installment_months not in INSTALLMENT_MONTHS:
        raise PaymentMethodError("Choose 3, 6, 12 or 24 months.")
    if method == Payment.Method.CARD and saved_card_id:
        # saved card: only the token goes to the bank; offered only to customers who paid recently
        saved = available_saved_cards(user).select_for_update().filter(pk=saved_card_id).first()
        if saved is None:
            raise payments.CardInvalid("saved_card", "This saved card is not available. Enter the card again.")
        result = payments.charge_token(saved, cvc, total)
    elif method == Payment.Method.CARD and card is not None:
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
    now = timezone.now()
    for item in cart:
        product = products[item.product_id]
        OrderItem.objects.create(order=order, product=product,
                                 quantity=item.quantity, unit_price=product.price)
        if not declined:                     # a declined payment does not take goods from the stock
            Product.objects.filter(id=product.id).update(
                stock_quantity=F("stock_quantity") - item.quantity)
    if promo and not declined:
        PromoCode.objects.filter(pk=promo.pk).update(used_count=F("used_count") + 1)
        PromoRedemption.objects.create(user=user, promo=promo, order=order)   # once per customer

    # 5b. Cards: remember the token (if the customer asked) and when the card was used
    if result is not None and result.approved:
        if saved is not None:
            saved.last_used_at = now
            saved.save(update_fields=["last_used_at"])
        elif save_card:
            month, year = payments.card_expiry(card)
            saved, _ = SavedCard.objects.update_or_create(
                user=user, brand=result.brand, last4=result.last4, exp_month=month, exp_year=year,
                defaults={"token": payments.new_token(), "holder": str(card.get("holder", "")).strip().upper()[:60],
                          "last_used_at": now})

    # 5c. QR and bank transfer must be paid in time, otherwise the order is cancelled automatically
    expires_at = None
    if pay_status == Payment.Status.PENDING and method == Payment.Method.QR:
        expires_at = now + timedelta(minutes=settings.PAYMENT_TIMEOUT_MINUTES)
    elif pay_status == Payment.Status.PENDING and method == Payment.Method.BANK_TRANSFER:
        expires_at = now + timedelta(hours=settings.BANK_TRANSFER_TIMEOUT_HOURS)

    payment = Payment.objects.create(
        order=order, method=method, amount=total, status=pay_status,
        paid_at=now if pay_status == Payment.Status.PAID else None,
        provider_reference=result.reference if result else f"SP-{order.pk:06d}",
        saved_card=saved, expires_at=expires_at,
        card_brand=result.brand if result else "", card_last4=result.last4 if result else "",
        failure_reason=result.reason if declined else "",
        installment_months=installment_months if method == Payment.Method.INSTALLMENT else None,
    )

    # 5d. QR: a one-time secret link for the phone (lives exactly as long as the payment timer)
    if method == Payment.Method.QR and expires_at:
        QrPayment.objects.create(payment=payment, token=secrets.token_urlsafe(24), expires_at=expires_at)

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
        mins = settings.PAYMENT_TIMEOUT_MINUTES
        texts[Order.Status.PENDING] = (f"Order #{n}: pay ${total} by QR within {mins} minutes.",
                                       f"Заказ №{n}: оплатите ${total} по QR в течение {mins} минут.",
                                       f"№{n} тапсырыс: ${total} соманы QR арқылы {mins} минут ішінде төлеңіз.")
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
    if payment.expires_at and payment.expires_at <= timezone.now():
        raise PaymentExpiredError("The payment time is over. The order is cancelled.")
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
    return _cancel(order)
    # If any step fails, ROLLBACK: the stock, order and payment stay as they were.


def _cancel(order: Order, expired: bool = False) -> Order:
    """Shared by "cancel" and "payment time is over". The order row is already locked."""
    # 2. Return every product to the stock (items already refunded are back already)
    restocked = []
    for item in order.items.select_for_update():
        back = item.quantity - item.refunded_quantity
        if back > 0:
            Product.objects.filter(id=item.product_id).update(stock_quantity=F("stock_quantity") + back)
            restocked.append(item.product_id)

    # 3. Order -> cancelled
    order.status = Order.Status.CANCELLED
    order.save(update_fields=["status", "updated_at"])

    # 4. Payment -> refunded (the rest of the money) or failed if it was never paid
    payment = Payment.objects.select_for_update().filter(order=order).first()
    refund_sum = Decimal("0")
    if payment:
        if payment.status == Payment.Status.PAID:
            refund_sum = payment.amount - payment.refunded_amount
            payment.status, payment.refunded_amount = Payment.Status.REFUNDED, payment.amount
        else:
            payment.status = Payment.Status.FAILED
            if expired:
                payment.failure_reason = "Payment time is over."
        payment.save(update_fields=["status", "refunded_amount", "failure_reason"])

    # 4b. The promo code use comes back (the customer may use the code again)
    if order.promo_code_id:
        PromoCode.objects.filter(pk=order.promo_code_id, used_count__gt=0).update(
            used_count=F("used_count") - 1)
        PromoRedemption.objects.filter(order=order).delete()

    # 5. Tell the customer; tell subscribers if a product is back in stock
    n = order.pk
    if expired:
        en = f"Order #{n} is cancelled: it was not paid in time. The items are back on sale."
        ru = f"Заказ №{n} отменён: оплата не поступила вовремя. Товары снова в продаже."
        kk = f"№{n} тапсырыс тоқтатылды: төлем уақытында түспеді. Тауарлар қайта сатылымда."
    elif refund_sum > 0:
        en = f"Order #{n} is cancelled. ${refund_sum} will be refunded."
        ru = f"Заказ №{n} отменён. ${refund_sum} будут возвращены."
        kk = f"№{n} тапсырыс тоқтатылды. ${refund_sum} қайтарылады."
    else:
        en, ru, kk = f"Order #{n} is cancelled.", f"Заказ №{n} отменён.", f"№{n} тапсырыс тоқтатылды."
    Notification.objects.create(user=order.user, order=order, link="/orders",
                                message=en, message_ru=ru, message_kk=kk)
    notify_back_in_stock(restocked)
    return order


# ---------------------------------------------------------------------
# PAYMENT TIMER - unpaid QR / bank transfer orders are cancelled automatically
# ---------------------------------------------------------------------
def expire_unpaid_orders(user=None) -> int:
    """Cancels every order whose payment time is over. Called by `manage.py expire_orders`
    and also at the start of order / payment requests ("lazy" check), so it works without cron."""
    now = timezone.now()
    qs = Order.objects.filter(status=Order.Status.PENDING, payment__status=Payment.Status.PENDING,
                              payment__expires_at__lte=now)
    if user is not None:
        qs = qs.filter(user=user)
    done = 0
    for order_id in list(qs.values_list("id", flat=True)):
        with transaction.atomic():
            order = Order.objects.select_for_update().get(pk=order_id)
            payment = Payment.objects.filter(order=order).first()
            # check again under the lock: maybe it was paid a second ago
            if (order.status == Order.Status.PENDING and payment and payment.status == Payment.Status.PENDING
                    and payment.expires_at and payment.expires_at <= timezone.now()):
                _cancel(order, expired=True)
                done += 1
    return done


# ---------------------------------------------------------------------
# REFUND - money back for some items of a paid order
# ---------------------------------------------------------------------
REFUNDABLE_STATUSES = (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)


@transaction.atomic
def refund_item(order: Order, item_id: int, quantity: int, reason: str = "other",
                comment: str = "", by=None) -> Refund:
    order = Order.objects.select_for_update().get(pk=order.pk)
    payment = Payment.objects.select_for_update().filter(order=order).first()
    if order.status not in REFUNDABLE_STATUSES or payment is None or payment.status != Payment.Status.PAID:
        raise RefundError("Only paid orders can be refunded.")
    item = order.items.select_for_update().filter(pk=item_id).select_related("product").first()
    if item is None:
        raise RefundError("This item is not in the order.")
    if reason not in Refund.Reason.values:
        reason = Refund.Reason.OTHER
    if not 1 <= quantity <= item.refundable_quantity:
        raise RefundError(f"You can return from 1 to {item.refundable_quantity} pcs.")

    # the promo discount is shared between all items, so the refund is the price minus that share
    full = order.total_amount + order.discount_amount
    share = order.total_amount / full if full else Decimal("1")
    amount = (item.unit_price * quantity * share).quantize(Decimal("0.01"))
    remaining = payment.amount - payment.refunded_amount
    left_after = sum(i.refundable_quantity for i in order.items.all()) - quantity
    if left_after == 0 or amount > remaining:
        amount = remaining            # the last refund returns exactly what is left (no lost cents)
    if amount <= 0:
        raise RefundError("Nothing left to refund.")

    item.refunded_quantity = F("refunded_quantity") + quantity
    item.save(update_fields=["refunded_quantity"])
    Product.objects.filter(id=item.product_id).update(stock_quantity=F("stock_quantity") + quantity)

    payment.refunded_amount = payment.refunded_amount + amount
    if payment.refunded_amount >= payment.amount:
        payment.status = Payment.Status.REFUNDED
    payment.save(update_fields=["refunded_amount", "status"])

    refund = Refund.objects.create(order=order, order_item=item, quantity=quantity, amount=amount,
                                   reason=reason, comment=comment[:200], created_by=by)
    p = item.product
    where_en = f" to {payment.card_brand.upper()} •••• {payment.card_last4}" if payment.card_last4 else ""
    where_ru = f" на {payment.card_brand.upper()} •••• {payment.card_last4}" if payment.card_last4 else ""
    where_kk = f" {payment.card_brand.upper()} •••• {payment.card_last4} картасына" if payment.card_last4 else ""
    Notification.objects.create(
        user=order.user, order=order, link="/orders",
        message=f"Refund for order #{order.pk}: {p.name_en} × {quantity} — ${amount}{where_en}.",
        message_ru=f"Возврат по заказу №{order.pk}: {p.name_ru or p.name_en} × {quantity} — ${amount}{where_ru}.",
        message_kk=f"№{order.pk} тапсырыс бойынша қайтару: {p.name_kk or p.name_en} × {quantity} — ${amount}{where_kk}.",
    )
    notify_back_in_stock([item.product_id])
    return refund


# ---------------------------------------------------------------------
# BACK IN STOCK - "tell me when it is available"
# ---------------------------------------------------------------------
def subscribe_stock(user, product: Product) -> StockSubscription:
    if product.stock_quantity > 0:
        raise StockSubscriptionError("This product is in stock - you can buy it now.")
    sub, _ = StockSubscription.objects.get_or_create(user=user, product=product, notified_at=None)
    return sub


def unsubscribe_stock(user, product_id: int) -> None:
    StockSubscription.objects.filter(user=user, product_id=product_id, notified_at=None).delete()


def notify_back_in_stock(product_ids) -> int:
    """Products that are back on sale -> a notification for every waiting customer."""
    product_ids = [pid for pid in set(product_ids) if pid]
    if not product_ids:
        return 0
    subs = list(StockSubscription.objects.filter(
        product_id__in=product_ids, notified_at=None,
        product__stock_quantity__gt=0, product__is_active=True).select_related("product"))
    for sub in subs:
        p = sub.product
        Notification.objects.create(
            user_id=sub.user_id, kind=Notification.Kind.SYSTEM, link=f"/product/{p.pk}",
            message=f"Back in stock: {p.name_en}. Hurry up!",
            message_ru=f"Снова в наличии: {p.name_ru or p.name_en}. Успейте купить!",
            message_kk=f"Қайта сатылымда: {p.name_kk or p.name_en}. Үлгеріп қалыңыз!",
        )
    StockSubscription.objects.filter(pk__in=[s.pk for s in subs]).update(notified_at=timezone.now())
    return len(subs)


# ---------------------------------------------------------------------
# SAVED CARDS - shown only to customers who paid by card recently
# ---------------------------------------------------------------------
def available_saved_cards(user):
    since = timezone.now() - timedelta(days=settings.SAVED_CARD_RECENT_DAYS)
    return SavedCard.objects.filter(user=user, last_used_at__gte=since)


# ---------------------------------------------------------------------
# TOP - only REAL paid purchases (demo orders from seed_shop are not counted)
# ---------------------------------------------------------------------
PAID_STATUSES = (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)
_NET_UNITS = Sum(F("quantity") - F("refunded_quantity"))


def _real_items(since=None, until=None):
    items = OrderItem.objects.filter(order__is_demo=False, order__status__in=PAID_STATUSES)
    if since:
        items = items.filter(order__created_at__gte=since)
    if until:
        items = items.filter(order__created_at__lt=until)
    return items


def top_hits(days=None, limit=12) -> list:
    """[(product_id, units)] most bought first; returned items are not counted."""
    since = timezone.now() - timedelta(days=days) if days else None
    rows = (_real_items(since).values("product_id").annotate(units=_NET_UNITS)
            .filter(units__gt=0).order_by("-units", "product_id")[:limit])
    return [(r["product_id"], r["units"]) for r in rows]


def top_trends(limit=12, window=7) -> list:
    """[(product_id, units this week, units the week before, growth %)] - fastest growing first."""
    now = timezone.now()
    cur = dict(_real_items(now - timedelta(days=window)).values("product_id").annotate(u=_NET_UNITS)
               .values_list("product_id", "u"))
    prev = dict(_real_items(now - timedelta(days=2 * window), now - timedelta(days=window))
                .values("product_id").annotate(u=_NET_UNITS).values_list("product_id", "u"))
    rows = []
    for pid, units in cur.items():
        before = prev.get(pid) or 0
        if units and units > before:
            growth = round((units - before) * 100 / before) if before else None   # None = new this week
            rows.append((pid, units, before, growth))
    rows.sort(key=lambda r: (-(r[1] - r[2]), -r[1], r[0]))
    return rows[:limit]


def top_new(limit=12):
    return Product.objects.filter(is_active=True).order_by("-created_at", "-id")[:limit]


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
    """Top products by units really bought by customers (demo, unpaid, cancelled and returned not counted)."""
    rows = (_real_items().values("product_id").annotate(units=_NET_UNITS, money=Sum(_LINE))
            .filter(units__gt=0).order_by("-units", "product_id")[:limit])
    found = {p.id: p for p in Product.objects.filter(id__in=[r["product_id"] for r in rows])}
    result = []
    for r in rows:
        p = found.get(r["product_id"])
        if p:
            p.units_sold, p.revenue = r["units"], r["money"]
            result.append(p)
    return result


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
# Demo orders (seed_shop) are left out unless demo=True.
# ---------------------------------------------------------------------
def _orders(since=None, demo=False):
    orders = Order.objects.all() if demo else Order.objects.filter(is_demo=False)
    return orders.filter(created_at__gte=since) if since else orders


def _sold_items(since=None, demo=False):
    items = OrderItem.objects.exclude(order__status__in=[Order.Status.CANCELLED, Order.Status.PENDING])
    if not demo:
        items = items.filter(order__is_demo=False)
    return items.filter(order__created_at__gte=since) if since else items


_LINE = ExpressionWrapper((F("quantity") - F("refunded_quantity")) * F("unit_price"),
                          output_field=DecimalField(max_digits=12, decimal_places=2))
_UNITS = Sum(F("quantity") - F("refunded_quantity"))


def report_summary(since=None, demo=False) -> dict:
    sold = _orders(since, demo).filter(status__in=PAID_STATUSES)
    totals = sold.aggregate(revenue=Sum("total_amount"), discounts=Sum("discount_amount"),
                            refunded=Sum("payment__refunded_amount"), count=Count("id"))
    count = totals["count"] or 0
    refunded = totals["refunded"] or Decimal("0")
    revenue = (totals["revenue"] or Decimal("0")) - refunded         # money the shop keeps
    cancelled = _orders(since, demo).filter(status=Order.Status.CANCELLED)
    return {
        "orders": count, "revenue": revenue, "discounts": totals["discounts"] or Decimal("0"),
        "refunded": refunded,
        "refund_count": Refund.objects.filter(order__in=_orders(since, demo)).count(),
        "avg_order": (revenue / count).quantize(Decimal("0.01")) if count else Decimal("0"),
        "units": _sold_items(since, demo).aggregate(n=_UNITS)["n"] or 0,
        "cancelled": cancelled.count(),
        "expired": cancelled.filter(payment__failure_reason="Payment time is over.").count(),
        "waiting": _orders(since, demo).filter(status=Order.Status.PENDING).count(),
    }


def report_sales_by_category(since=None, demo=False) -> list:
    """[{category, units, revenue, share%}] - before promo discounts, returned items not counted."""
    rows = list(_sold_items(since, demo).values("product__category__id", "product__category__name_ru",
                                                "product__category__name_en")
                .annotate(units=_UNITS, revenue=Sum(_LINE)).filter(units__gt=0).order_by("-revenue"))
    total = sum((r["revenue"] for r in rows), Decimal("0"))
    for r in rows:
        r["name"] = r["product__category__name_ru"] or r["product__category__name_en"]
        r["share"] = round(float(r["revenue"] / total * 100), 1) if total else 0
    return rows


def report_best_sellers(since=None, limit=10, demo=False) -> list:
    return list(_sold_items(since, demo).values("product__id", "product__sku", "product__name_ru",
                                                "product__name_en", "product__stock_quantity")
                .annotate(units=_UNITS, revenue=Sum(_LINE)).filter(units__gt=0)
                .order_by("-units", "-revenue")[:limit])


def report_refunds(since=None, demo=False, limit=10):
    return (Refund.objects.filter(order__in=_orders(since, demo))
            .select_related("order", "order_item__product", "created_by")[:limit])


def report_low_stock(threshold=10):
    """Active products with stock below the threshold, emptiest first."""
    return (Product.objects.filter(is_active=True, stock_quantity__lt=threshold)
            .select_related("category").order_by("stock_quantity", "name_en"))


def report_promo_usage(since=None, demo=False) -> list:
    orders = _orders(since, demo).exclude(status=Order.Status.CANCELLED).filter(promo_code__isnull=False)
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
def check_promo(code: str, order_total: Decimal, lock: bool = False, user=None) -> PromoCode:
    """Returns the PromoCode or raises PromoCodeError with the reason.
    With `user`: the same customer cannot use a code twice (also a UNIQUE rule in the database)."""
    code = (code or "").strip().upper()
    qs = PromoCode.objects.select_for_update() if lock else PromoCode.objects
    promo = qs.filter(code=code, is_active=True).first()
    now = timezone.now()
    if promo is None:
        raise PromoCodeError("Promo code not found.", "not_found")
    if promo.valid_from and now < promo.valid_from:
        raise PromoCodeError("Promo code is not active yet.", "not_active")
    if promo.valid_until and now > promo.valid_until:
        raise PromoCodeError("Promo code has expired.", "expired")
    if promo.max_uses is not None and promo.used_count >= promo.max_uses:
        raise PromoCodeError("Promo code has been used up.", "used_up")
    if user is not None and PromoRedemption.objects.filter(user=user, promo=promo).exists():
        raise PromoCodeError("You have already used this promo code.", "already_used")
    if order_total < promo.min_order_amount:
        raise PromoCodeError(f"Minimum order for this code is ${promo.min_order_amount}.", "min_order")
    return promo


def discount_for(promo: PromoCode, total: Decimal) -> Decimal:
    return (total * promo.discount_percent / Decimal(100)).quantize(Decimal("0.01"))


def cart_total(user) -> Decimal:
    return sum((i.product.price * i.quantity
                for i in CartItem.objects.filter(user=user).select_related("product")), Decimal("0"))


# ---------------------------------------------------------------------
# QR SCAN - the phone opens /pay/<token>, the customer confirms, the order becomes paid
# ---------------------------------------------------------------------
class QrError(Exception):
    """code: not_found, expired, already_paid, cancelled"""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


def qr_state(qr: QrPayment) -> str:
    order = qr.payment.order
    if qr.paid_at or qr.payment.status == Payment.Status.PAID:
        return "paid"
    if order.status == Order.Status.CANCELLED:
        return "expired" if qr.payment.failure_reason == "Payment time is over." else "cancelled"
    if qr.expires_at <= timezone.now():
        return "expired"
    return "pending"


def device_name(user_agent: str) -> str:
    """A short, human name of the phone or computer from the browser's User-Agent."""
    ua = user_agent or ""
    device = next((name for key, name in (("iPhone", "iPhone"), ("iPad", "iPad"), ("Android", "Android"),
                                          ("Macintosh", "Mac"), ("Windows", "Windows"), ("Linux", "Linux"))
                   if key in ua), "Device")
    browser = next((name for key, name in (("YaBrowser", "Yandex"), ("Edg", "Edge"), ("OPR", "Opera"),
                                           ("Chrome", "Chrome"), ("CriOS", "Chrome"), ("Firefox", "Firefox"),
                                           ("Safari", "Safari"))
                    if re.search(key, ua)), "")
    return f"{device} · {browser}" if browser else device


@transaction.atomic
def pay_by_qr(token: str, user_agent: str = "") -> QrPayment:
    qr = (QrPayment.objects.select_for_update().select_related("payment__order")
          .filter(token=token).first())
    if qr is None:
        raise QrError("not_found")
    state = qr_state(qr)
    if state != "pending":
        raise QrError(state)
    try:
        confirm_payment(qr.payment.order)
    except PaymentExpiredError:
        raise QrError("expired")
    qr.paid_at = timezone.now()
    qr.paid_device = device_name(user_agent)[:80]
    qr.save(update_fields=["paid_at", "paid_device"])
    return qr


# ---------------------------------------------------------------- review photos
class ReviewPhotoError(Exception):
    pass


# the first bytes of a file show its real type (a renamed .exe will not pass)
_IMAGE_SIGNATURES = (
    (b"\xff\xd8\xff", "jpg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
)


def image_type(uploaded):
    head = uploaded.read(12)
    uploaded.seek(0)
    for sig, kind in _IMAGE_SIGNATURES:
        if head.startswith(sig):
            return kind
    if head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "webp"
    return None


def validate_review_photos(files):
    from django.conf import settings
    from .models import REVIEW_PHOTOS_MAX
    if len(files) > REVIEW_PHOTOS_MAX:
        raise ReviewPhotoError(f"You can add up to {REVIEW_PHOTOS_MAX} photos.")
    max_bytes = settings.REVIEW_PHOTO_MAX_MB * 1024 * 1024
    for f in files:
        if f.size > max_bytes:
            raise ReviewPhotoError(f"Each photo must be smaller than {settings.REVIEW_PHOTO_MAX_MB} MB.")
        if not image_type(f):
            raise ReviewPhotoError("Only JPG, PNG or WEBP photos.")


@transaction.atomic
def add_review_photos(review, files):
    from .models import ReviewPhoto
    for position, f in enumerate(files):
        f.name = f"review{review.pk}_{position}.{image_type(f)}"   # our own safe file name
        ReviewPhoto.objects.create(review=review, image=f, position=position)
