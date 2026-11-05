"""
REST API for the Angular frontend.  All addresses start with /api/
Login uses JWT tokens: the frontend sends  Authorization: Bearer <access token>
"""
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Avg, Count, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken

from . import services
from .models import Address, CartItem, Category, Order, Product, Review
from .serializers import (
    AddressSerializer, CartItemSerializer, CategorySerializer, OrderSerializer,
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


@api_view(["GET"])
@permission_classes([AllowAny])
def products(request):
    """GET /api/products/?category=1&q=mouse&sort=price|-price|name"""
    qs = _products()
    if request.GET.get("category"):
        qs = qs.filter(category_id=request.GET["category"])
    text = request.GET.get("q", "").strip()
    if text:
        qs = qs.filter(Q(name_en__icontains=text) | Q(name_ru__icontains=text)
                       | Q(name_kk__icontains=text) | Q(sku__icontains=text))
    sort = request.GET.get("sort")
    qs = qs.order_by({"price": "price", "-price": "-price", "name": "name_en"}.get(sort, "-id"))  # newest first
    return Response(ProductSerializer(qs, many=True).data)


@api_view(["GET"])
@permission_classes([AllowAny])
def product_detail(request, pk):
    product = get_object_or_404(_products().prefetch_related("reviews__user"), pk=pk)
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
    serializer.save(user=request.user, product=product)
    return Response(serializer.data, status=201)


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
    if method not in ("card", "bank_transfer", "cash_on_delivery"):
        return Response({"detail": "Unknown payment method."}, status=400)
    try:
        order = services.place_order(request.user, address, method)
    except (services.OutOfStockError, services.EmptyCartError) as e:
        return Response({"detail": str(e)}, status=400)
    return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def my_orders(request):
    qs = (Order.objects.filter(user=request.user).select_related("payment")
          .prefetch_related("items__product__category"))
    return Response(OrderSerializer(qs, many=True).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def cancel_order(request, pk):
    """POST /api/orders/<id>/cancel/ - cancel own order and refund the payment."""
    order = get_object_or_404(Order, pk=pk, user=request.user)
    try:
        order = services.cancel_order(order)
    except services.CancelNotAllowedError as e:
        return Response({"detail": str(e)}, status=400)
    order = Order.objects.select_related("payment").prefetch_related("items__product__category").get(pk=order.pk)
    return Response(OrderSerializer(order).data)


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
