"""
REST API for the Angular frontend.  All addresses start with /api/
Login uses JWT tokens: the frontend sends  Authorization: Bearer <access token>
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Avg, Count, Max, Min, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from . import payments, services
from .models import Address, CartItem, Category, City, Favorite, Notification, Order, Product, Review, StockSubscription
from .serializers import (
    AddressSerializer, CartItemSerializer, CategorySerializer, CitySerializer, NotificationSerializer, OrderSerializer,
    SavedCardSerializer,
    ProductDetailSerializer, ProductSerializer, RegisterSerializer, ReviewSerializer,
    UserSerializer,
)


def _products():
    return (Product.objects.filter(is_active=True).select_related("category")
            .annotate(avg_rating=Avg("reviews__rating"), review_count=Count("reviews", distinct=True)))


def _tokens(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


# ---------------------------------------------------------------- catalogue
@api_view(["GET"])
@permission_classes([AllowAny])
def categories(request):
    qs = Category.objects.filter(is_active=True).order_by("id").annotate(
        product_count=Count("products", filter=Q(products__is_active=True)))
    return Response(CategorySerializer(qs, many=True).data)


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _decimal(value):
    try:
        return Decimal(value) if value not in (None, "") else None
    except InvalidOperation:
        return None


SORTS = {
    "price": ("price",), "-price": ("-price",), "name": ("name_en",), "new": ("-id",),
    "rating": ("-avg_rating", "-review_count"),     # best rated first (products without reviews last)
    "popular": ("-sold", "-id"),                    # most bought first
}


@api_view(["GET"])
@permission_classes([AllowAny])
def products(request):
    """GET /api/products/?q=&category=1&brand=Apple,Nike&min_price=10&max_price=200
                          &min_rating=4&in_stock=1&sort=price|-price|name|new|rating|popular"""
    qs = _products()
    g = request.GET
    if g.get("category"):
        qs = qs.filter(category_id=g["category"])
    text = g.get("q", "").strip()
    if text:
        qs = qs.filter(Q(name_en__icontains=text) | Q(name_ru__icontains=text)
                       | Q(name_kk__icontains=text) | Q(sku__icontains=text) | Q(brand__icontains=text))
    brands = [b.strip() for b in g.get("brand", "").split(",") if b.strip()]
    if brands:
        qs = qs.filter(brand__in=brands)
    if (low := _decimal(g.get("min_price"))) is not None:
        qs = qs.filter(price__gte=low)
    if (high := _decimal(g.get("max_price"))) is not None:
        qs = qs.filter(price__lte=high)
    if (rating := _decimal(g.get("min_rating"))) is not None:
        qs = qs.filter(avg_rating__gte=rating)
    if g.get("in_stock") in ("1", "true"):
        qs = qs.filter(stock_quantity__gt=0)
    sort = g.get("sort", "new")
    if sort == "popular":
        # subquery, so the JOIN with reviews does not multiply the numbers
        from django.db.models import IntegerField, OuterRef, Subquery, Sum
        from django.db.models.functions import Coalesce
        from .models import OrderItem
        sold = (OrderItem.objects.filter(product=OuterRef("pk")).exclude(order__status="cancelled")
                .values("product").annotate(n=Sum("quantity")).values("n"))
        qs = qs.annotate(sold=Coalesce(Subquery(sold, output_field=IntegerField()), 0))
    if sort == "rating":
        from django.db.models import F
        qs = qs.order_by(F("avg_rating").desc(nulls_last=True), "-review_count")
    else:
        qs = qs.order_by(*SORTS.get(sort, ("-id",)))
    return Response(ProductSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def product_filters(request):
    """GET /api/products/filters/?category=1 -> brands and price range for the filter panel"""
    qs = Product.objects.filter(is_active=True)
    if request.GET.get("category"):
        qs = qs.filter(category_id=request.GET["category"])
    prices = qs.aggregate(min=Min("price"), max=Max("price"))
    brands = (qs.exclude(brand="").values("brand").annotate(count=Count("id")).order_by("brand"))
    return Response({"min_price": str(prices["min"] or "0.00"), "max_price": str(prices["max"] or "0.00"),
                     "brands": list(brands)})


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail(request, pk):
    product = get_object_or_404(_products().prefetch_related("reviews__user", "reviews__photos", "images"), pk=pk)
    return Response(ProductDetailSerializer(product).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def best_sellers(request):
    """GET /api/products/best-sellers/?limit=4  (1..12)"""
    try:
        limit = max(1, min(12, int(request.GET.get("limit", 4))))
    except ValueError:
        limit = 4
    ids = [p.id for p in services.best_sellers(limit=limit)]
    found = {p.id: p for p in _products().filter(id__in=ids)}
    return Response(ProductSerializer([found[i] for i in ids if i in found], many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def search(request):
    """Search across products, categories and (for logged-in users) orders."""
    user = request.user if request.user.is_authenticated else None
    result = services.search(request.GET.get("q", ""), user=user)
    ids = [p.id for p in result["products"]]
    products = _products().filter(id__in=ids).order_by("id")      # with rating and review count
    return Response({
        "products": ProductSerializer(products, many=True).data,
        "categories": CategorySerializer(result["categories"], many=True).data,
        "orders": OrderSerializer(result["orders"], many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def add_review(request, pk):
    product = get_object_or_404(Product, pk=pk, is_active=True)
    if Review.objects.filter(user=request.user, product=product).exists():
        return Response({"detail": "You have already reviewed this product."}, status=400)
    serializer = ReviewSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    photos = request.FILES.getlist("photos")      # sent as multipart/form-data, up to 3
    try:
        services.validate_review_photos(photos)
    except services.ReviewPhotoError as e:
        return Response({"photos": [str(e)]}, status=400)
    with transaction.atomic():
        review = serializer.save(user=request.user, product=product)
        services.add_review_photos(review, photos)
    return Response(ReviewSerializer(review).data, status=201)


# ---------------------------------------------------------------- accounts
@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    data = RegisterSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    v = data.validated_data
    try:
        user = services.register_customer(v["username"], v["email"], v["password"],
                                          first_name=v.get("first_name", ""))
    except DjangoValidationError as e:          # weak password
        return Response({"password": e.messages}, status=400)
    return Response({"user": UserSerializer(user).data, **_tokens(user)}, status=201)


@api_view(["GET"])
@permission_classes([AllowAny])
def cities(request):
    """GET /api/cities/ -> cities we deliver to, with delivery days."""
    return Response(CitySerializer(City.objects.filter(is_active=True), many=True).data)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticated])
def me(request):
    if request.method == "PATCH":
        s = UserSerializer(request.user, data=request.data, partial=True)
        s.is_valid(raise_exception=True)
        s.save()
    return Response(UserSerializer(request.user).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def addresses(request):
    if request.method == "POST":
        s = AddressSerializer(data=request.data)
        s.is_valid(raise_exception=True)
        mine = Address.objects.filter(user=request.user)
        make_default = s.validated_data.get("is_default") or not mine.exists()
        if make_default:
            mine.update(is_default=False)
        s.save(user=request.user, is_default=make_default)
        return Response(s.data, status=201)
    qs = Address.objects.filter(user=request.user).order_by("-is_default", "id")
    return Response(AddressSerializer(qs, many=True).data)


# ---------------------------------------------------------------- favorites
def _favorites_response(user):
    """Liked products, newest like first (with rating and review count)."""
    ids = list(Favorite.objects.filter(user=user).values_list("product_id", flat=True))
    found = {p.id: p for p in _products().filter(id__in=ids)}
    return Response(ProductSerializer([found[i] for i in ids if i in found], many=True).data)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def favorites(request):
    """GET - list of liked products. POST {product_id} - like a product."""
    if request.method == "POST":
        product = get_object_or_404(Product, pk=request.data.get("product_id"), is_active=True)
        Favorite.objects.get_or_create(user=request.user, product=product)
    return _favorites_response(request.user)


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def remove_favorite(request, product_id):
    """DELETE /api/favorites/<product_id>/ - remove the like."""
    Favorite.objects.filter(user=request.user, product_id=product_id).delete()
    return _favorites_response(request.user)


# ---------------------------------------------------------------- cart & orders
def _cart_response(user):
    items = CartItem.objects.filter(user=user).select_related("product__category").order_by("id")
    total = sum((i.line_total for i in items), 0)
    return Response({"items": CartItemSerializer(items, many=True).data,
                     "total": f"{total:.2f}", "count": sum(i.quantity for i in items)})


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def cart(request):
    """POST {product_id, quantity}: sets the quantity (0 removes the product)."""
    if request.method == "POST":
        product = get_object_or_404(Product, pk=request.data.get("product_id"), is_active=True)
        try:
            qty = int(request.data.get("quantity", 1))
        except (TypeError, ValueError):
            return Response({"detail": "Quantity must be a number."}, status=400)
        if qty <= 0:
            CartItem.objects.filter(user=request.user, product=product).delete()
        elif qty > product.stock_quantity:
            return Response({"detail": f"Only {product.stock_quantity} left in stock."}, status=400)
        else:
            CartItem.objects.update_or_create(user=request.user, product=product,
                                              defaults={"quantity": qty})
    return _cart_response(request.user)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def checkout(request):
    """POST {address_id, method}"""
    address = get_object_or_404(Address, pk=request.data.get("address_id"), user=request.user)
    method = request.data.get("method", "card")
    if method not in ("card", "bank_transfer", "cash_on_delivery", "qr", "installment"):
        return Response({"detail": "Unknown payment method."}, status=400)
    saved_card_id = _int(request.data.get("saved_card_id")) if method == "card" else None
    card = request.data.get("card") if method == "card" and not saved_card_id else None
    if method == "card" and not saved_card_id and not isinstance(card, dict):
        return Response({"detail": "Enter the card details.", "field": "number"}, status=400)
    services.expire_unpaid_orders(user=request.user)
    try:
        order = services.place_order(request.user, address, method,
                                     promo_code=request.data.get("promo_code", ""), card=card,
                                     installment_months=_int(request.data.get("installment_months")),
                                     saved_card_id=saved_card_id, cvc=str(request.data.get("cvc", "")),
                                     save_card=bool(request.data.get("save_card")))
    except payments.CardInvalid as e:
        return Response({"detail": str(e), "field": e.field}, status=400)
    except services.PromoCodeError as e:
        return Response({"detail": str(e), "code": e.code}, status=400)
    except (services.OutOfStockError, services.EmptyCartError, services.PaymentMethodError) as e:
        return Response({"detail": str(e)}, status=400)
    data = OrderSerializer(_order_qs().get(pk=order.pk)).data
    if order.status == Order.Status.CANCELLED:          # the bank declined the card
        return Response({"detail": "The bank declined the payment: " + order.payment.failure_reason,
                         "code": "card_declined", "order": data}, status=402)
    return Response(data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_orders(request):
    services.expire_unpaid_orders(user=request.user)        # "lazy" payment timer
    return Response(OrderSerializer(_order_qs().filter(user=request.user), many=True).data)


def _order_qs():
    return (Order.objects.select_related("payment", "payment__qr", "promo_code")
            .prefetch_related("items__product__category", "refunds__order_item__product"))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    """POST /api/orders/<id>/cancel/ - cancel own order and refund the payment."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        order = services.cancel_order(order)
    except services.CancelNotAllowedError as e:
        return Response({"detail": str(e)}, status=400)
    return Response(OrderSerializer(_order_qs().get(pk=order.pk)).data)


@api_view(["POST"])
@permission_classes([AllowAny])
def assistant(request):
    """POST /api/assistant/ {message, lang} -> {text, products, suggestions}"""
    from .assistant import reply
    user = request.user if request.user.is_authenticated else None
    result = reply(str(request.data.get("message", ""))[:300], request.data.get("lang", "en"), user)
    return Response({
        "text": result["text"],
        "products": ProductSerializer(result["products"], many=True).data,
        "suggestions": result["suggestions"],
    })


# ---------------------------------------------------------------- promo codes
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def promo_check(request):
    """POST {code} -> discount for the current cart (nothing is saved)"""
    total = services.cart_total(request.user)
    try:
        promo = services.check_promo(request.data.get("code", ""), total, user=request.user)
    except services.PromoCodeError as e:
        return Response({"valid": False, "detail": str(e), "code": e.code}, status=400)
    discount = services.discount_for(promo, total)
    return Response({"valid": True, "code": promo.code, "percent": promo.discount_percent,
                     "subtotal": f"{total:.2f}", "discount": f"{discount:.2f}",
                     "total": f"{total - discount:.2f}"})


# ---------------------------------------------------------------- notifications
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def notifications(request):
    """GET /api/notifications/ -> {unread, items: last 20}"""
    mine = Notification.objects.filter(user=request.user)
    return Response({
        "unread": mine.filter(is_read=False).count(),
        "items": NotificationSerializer(mine.order_by("-created_at")[:20], many=True).data,
    })


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notification_read(request, pk):
    """POST /api/notifications/<id>/read/"""
    updated = Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    if not updated:
        return Response({"detail": "Not found."}, status=404)
    return Response({"ok": True})


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def notifications_read_all(request):
    """POST /api/notifications/read-all/"""
    n = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({"marked": n})



# ---------------------------------------------------------------- QR payment (demo)
@api_view(["POST"])
@permission_classes([IsAuthenticated])
def pay_qr(request, pk):
    """POST /api/orders/<id>/pay-qr/ - demo: the customer has paid in the bank app.
    In a real shop the bank calls the shop's server; here the button plays the bank."""
    order = get_object_or_404(Order, pk=pk, user=request.user, payment__method="qr")
    services.expire_unpaid_orders(user=request.user)
    try:
        services.confirm_payment(order)
    except services.PaymentExpiredError as e:
        return Response({"detail": str(e), "code": "expired", "order": OrderSerializer(_order_qs().get(pk=pk)).data},
                        status=400)
    except services.OrderTransitionError as e:
        return Response({"detail": str(e), "code": "not_pending",
                         "order": OrderSerializer(_order_qs().get(pk=pk)).data}, status=400)
    return Response(OrderSerializer(_order_qs().get(pk=pk)).data)


# ---------------------------------------------------------------- top: hits, new, trends (real data only)
TOP_PERIODS = {"7": 7, "30": 30, "90": 90, "all": None}


@api_view(["GET"])
@permission_classes([AllowAny])
def top(request):
    """GET /api/top/?kind=hits|new|trends&period=7|30|90|all
    Hits and trends count only real paid purchases of customers (no demo orders)."""
    kind = request.GET.get("kind", "hits")
    if kind == "new":
        products = list(services.top_new(limit=12))
        found = {p.id: p for p in _products().filter(id__in=[p.id for p in products])}
        return Response({"kind": kind, "items": [{"product": ProductSerializer(found[p.id]).data}
                                                  for p in products if p.id in found]})
    if kind == "trends":
        rows = services.top_trends(limit=12)
        found = {p.id: p for p in _products().filter(id__in=[r[0] for r in rows])}
        return Response({"kind": kind, "items": [
            {"product": ProductSerializer(found[pid]).data, "units": units, "prev_units": before, "growth": growth}
            for pid, units, before, growth in rows if pid in found]})
    days = TOP_PERIODS.get(request.GET.get("period", "30"), 30)
    rows = services.top_hits(days=days, limit=12)
    found = {p.id: p for p in _products().filter(id__in=[r[0] for r in rows])}
    return Response({"kind": "hits", "items": [{"product": ProductSerializer(found[pid]).data, "units": units}
                                               for pid, units in rows if pid in found]})


# ---------------------------------------------------------------- back in stock
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def stock_alerts(request):
    """GET /api/stock-alerts/ -> ids of products the customer waits for"""
    ids = StockSubscription.objects.filter(user=request.user, notified_at=None).values_list("product_id", flat=True)
    return Response({"product_ids": list(ids)})


@api_view(["POST", "DELETE"])
@permission_classes([IsAuthenticated])
def notify_me(request, pk):
    """POST - tell me when the product is back. DELETE - I do not wait any more."""
    product = get_object_or_404(Product, pk=pk, is_active=True)
    if request.method == "DELETE":
        services.unsubscribe_stock(request.user, product.pk)
        return Response({"subscribed": False})
    try:
        services.subscribe_stock(request.user, product)
    except services.StockSubscriptionError as e:
        return Response({"detail": str(e), "code": "in_stock"}, status=400)
    return Response({"subscribed": True}, status=201)


# ---------------------------------------------------------------- saved cards
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def saved_cards(request):
    """GET /api/cards/ - saved cards, only if the customer paid by card recently"""
    from django.conf import settings
    return Response({"recent_days": settings.SAVED_CARD_RECENT_DAYS,
                     "cards": SavedCardSerializer(services.available_saved_cards(request.user), many=True).data})


@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_card(request, pk):
    from .models import SavedCard
    deleted, _ = SavedCard.objects.filter(pk=pk, user=request.user).delete()
    if not deleted:
        return Response({"detail": "Not found."}, status=404)
    return Response(status=204)


# ---------------------------------------------------------------- QR scanned with a phone
def _qr_data(qr):
    order = qr.payment.order
    return {"order_id": order.pk, "amount": f"{qr.payment.amount:.2f}", "shop": "Sauda",
            "items": sum(i.quantity for i in order.items.all()), "state": services.qr_state(qr),
            "expires_at": qr.expires_at, "created_at": qr.created_at, "paid_at": qr.paid_at,
            "paid_device": qr.paid_device}


@api_view(["GET"])
@permission_classes([AllowAny])
def qr_info(request, token):
    """GET /api/qr/<token>/ - what the phone shows. The secret token itself is the permission
    (like a real payment link), no login on the phone is needed."""
    from .models import QrPayment
    services.expire_unpaid_orders()
    qr = QrPayment.objects.select_related("payment__order").filter(token=token).first()
    if qr is None:
        return Response({"state": "not_found"}, status=404)
    return Response(_qr_data(qr))


@api_view(["POST"])
@permission_classes([AllowAny])
def qr_pay(request, token):
    """POST /api/qr/<token>/pay/ - the customer confirmed on the phone (demo bank)."""
    services.expire_unpaid_orders()
    try:
        qr = services.pay_by_qr(token, request.META.get("HTTP_USER_AGENT", ""))
    except services.QrError as e:
        return Response({"state": e.code}, status=404 if e.code == "not_found" else 409)
    return Response(_qr_data(qr))


@api_view(["GET"])
@permission_classes([AllowAny])
def network(request):
    """GET /api/network/ -> the laptop's address in the Wi-Fi, so the QR link opens on a phone
    even when the website itself was opened as http://localhost:4200."""
    import socket
    ip = ""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))        # no data is sent, it only picks the Wi-Fi interface
            ip = s.getsockname()[0]
    except OSError:
        pass
    return Response({"lan_ip": "" if ip.startswith("127.") else ip})
