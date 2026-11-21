"""
Serializers turn database rows into JSON for the Angular frontend (and back).
"""
from rest_framework import serializers

from .models import (
    Address, CartItem, Category, City, Notification, Order, OrderItem, Product, Refund, Review, SavedCard, User,
)


class CategorySerializer(serializers.ModelSerializer):
    product_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Category
        fields = ["id", "name_en", "name_ru", "name_kk", "product_count"]


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    avg_rating = serializers.FloatField(read_only=True, required=False)
    review_count = serializers.IntegerField(read_only=True, required=False)

    class Meta:
        model = Product
        fields = [
            "id", "sku", "name_en", "name_ru", "name_kk",
            "description_en", "description_ru", "description_kk",
            "price", "stock_quantity", "brand", "image_url", "category", "avg_rating", "review_count",
            "created_at",
        ]


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    photos = serializers.SerializerMethodField()

    class Meta:
        model = Review
        fields = ["id", "username", "rating", "comment", "created_at", "photos"]
        read_only_fields = ["id", "username", "created_at", "photos"]

    def get_photos(self, review):
        # relative address (/media/...): works on localhost, in Wi-Fi and through a tunnel link
        return [p.image.url for p in review.photos.all()]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be from 1 to 5.")
        return value


class ProductDetailSerializer(ProductSerializer):
    reviews = ReviewSerializer(many=True, read_only=True)
    images = serializers.SerializerMethodField()

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ["reviews", "images"]

    def get_images(self, product):
        """Main photo first, then the gallery (product_images) without repeats."""
        urls = [product.image_url] if product.image_url else []
        for img in product.images.all():
            if img.url not in urls:
                urls.append(img.url)
        return urls


class CitySerializer(serializers.ModelSerializer):
    class Meta:
        model = City
        fields = ["id", "name_en", "name_ru", "name_kk", "delivery_days_min", "delivery_days_max"]


class UserSerializer(serializers.ModelSerializer):
    city = CitySerializer(read_only=True)
    city_id = serializers.PrimaryKeyRelatedField(
        source="city", queryset=City.objects.filter(is_active=True), write_only=True, required=False, allow_null=True)

    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone",
                  "role", "preferred_language", "city", "city_id"]
        read_only_fields = ["id", "username", "role"]


class RegisterSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("This email is already registered.")
        return value


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = ["id", "label", "city", "street", "apartment", "postal_code", "is_default"]


class CartItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = CartItem
        fields = ["id", "product", "quantity", "line_total"]


class OrderItemSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    line_total = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = OrderItem
        fields = ["id", "product", "quantity", "unit_price", "line_total", "refunded_quantity"]


class RefundSerializer(serializers.ModelSerializer):
    product_id = serializers.IntegerField(source="order_item.product_id", read_only=True)
    name_en = serializers.CharField(source="order_item.product.name_en", read_only=True)
    name_ru = serializers.CharField(source="order_item.product.name_ru", read_only=True)
    name_kk = serializers.CharField(source="order_item.product.name_kk", read_only=True)

    class Meta:
        model = Refund
        fields = ["id", "product_id", "name_en", "name_ru", "name_kk", "quantity", "amount", "reason", "created_at"]


class SavedCardSerializer(serializers.ModelSerializer):
    """Only what is safe to show: type, last 4 digits, expiry. The token is never sent to the browser."""

    class Meta:
        model = SavedCard
        fields = ["id", "brand", "last4", "holder", "exp_month", "exp_year", "last_used_at"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment_method = serializers.CharField(source="payment.method", read_only=True, default=None)
    payment_status = serializers.CharField(source="payment.status", read_only=True, default=None)
    promo = serializers.CharField(source="promo_code.code", read_only=True, default=None)
    card_brand = serializers.CharField(source="payment.card_brand", read_only=True, default="")
    card_last4 = serializers.CharField(source="payment.card_last4", read_only=True, default="")
    installment_months = serializers.IntegerField(source="payment.installment_months", read_only=True, default=None)
    expires_at = serializers.DateTimeField(source="payment.expires_at", read_only=True, default=None)
    refunded_amount = serializers.DecimalField(source="payment.refunded_amount", max_digits=12,
                                               decimal_places=2, read_only=True, default="0.00")
    failure_reason = serializers.CharField(source="payment.failure_reason", read_only=True, default="")
    refunds = RefundSerializer(many=True, read_only=True)
    qr_token = serializers.SerializerMethodField()
    qr_paid_device = serializers.SerializerMethodField()

    def get_qr_token(self, order):
        qr = getattr(getattr(order, "payment", None), "qr", None)
        return qr.token if qr and order.status == "pending" else None

    def get_qr_paid_device(self, order):
        qr = getattr(getattr(order, "payment", None), "qr", None)
        return qr.paid_device if qr and qr.paid_at else ""

    class Meta:
        model = Order
        fields = ["id", "status", "shipping_address", "total_amount", "discount_amount", "promo",
                  "created_at", "items", "payment_method", "payment_status", "card_brand", "card_last4",
                  "installment_months", "expires_at", "refunded_amount", "failure_reason", "refunds",
                  "qr_token", "qr_paid_device"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "message", "message_ru", "message_kk", "link", "order", "is_read", "created_at"]
