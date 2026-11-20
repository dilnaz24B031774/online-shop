"""
Serializers turn database rows into JSON for the Angular frontend (and back).
"""
import re
import unicodedata

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.serializers import TokenRefreshSerializer

from .models import Address, CartItem, Category, Notification, Order, OrderItem, Product, Review, User


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
        ]


class ReviewSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)
    user_id = serializers.IntegerField(read_only=True)

    class Meta:
        model = Review
        fields = ["id", "user_id", "username", "rating", "comment", "created_at"]
        read_only_fields = ["id", "user_id", "username", "created_at"]

    def validate_rating(self, value):
        if not 1 <= value <= 5:
            raise serializers.ValidationError("Rating must be from 1 to 5.")
        return value


class ProductDetailSerializer(ProductSerializer):
    reviews = ReviewSerializer(many=True, read_only=True)

    class Meta(ProductSerializer.Meta):
        fields = ProductSerializer.Meta.fields + ["reviews"]


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email", "first_name", "last_name", "phone",
                  "role", "preferred_language", "preferred_currency"]
        read_only_fields = ["id", "role"]

    # Accept common phone formatting, but save a consistent digit-only value.
    phone = serializers.CharField(max_length=40, required=False, allow_blank=True)

    def validate_username(self, value):
        others = User.objects.filter(username__iexact=value)
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value

    def validate_email(self, value):
        others = User.objects.filter(email__iexact=value)
        if self.instance:
            others = others.exclude(pk=self.instance.pk)
        if others.exists():
            raise serializers.ValidationError("This email is already registered.")
        return value

    def validate_phone(self, value):
        if not value:
            return ""
        if not re.fullmatch(r"\+?[0-9 ()-]+", value):
            raise serializers.ValidationError("Enter a phone number with 7 to 15 digits.")
        digits = re.sub(r"[^0-9]", "", value)
        if not 7 <= len(digits) <= 15:
            raise serializers.ValidationError("Enter a phone number with 7 to 15 digits.")
        return ("+" if value.startswith("+") else "") + digits

    def _validate_name(self, value):
        if any(unicodedata.category(char).startswith("C") for char in value):
            raise serializers.ValidationError("Enter a name without control characters.")
        return value

    def validate_first_name(self, value):
        return self._validate_name(value)

    def validate_last_name(self, value):
        return self._validate_name(value)

    def update(self, instance, validated_data):
        # A profile request may have loaded its user before another request
        # changed the password. Never write that stale password (or other
        # untouched fields) back when saving only profile changes.
        for field, value in validated_data.items():
            setattr(instance, field, value)
        if validated_data:
            instance.save(update_fields=list(validated_data))
        return instance


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)
    new_password_confirm = serializers.CharField(write_only=True, trim_whitespace=False, max_length=4096)

    def validate(self, attrs):
        user = self.context["user"]
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError({"current_password": "The current password is incorrect."})
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "The passwords do not match."})
        if user.check_password(attrs["new_password"]):
            raise serializers.ValidationError({"new_password": "Choose a password different from your current password."})
        try:
            validate_password(attrs["new_password"], user=user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": error.messages}) from error
        return attrs


class PasswordAwareTokenRefreshSerializer(TokenRefreshSerializer):
    """SimpleJWT 5.3 checks password changes on access, but not on refresh."""

    def validate(self, attrs):
        refresh = self.token_class(attrs["refresh"])
        # Use the same active-user and password-hash checks as access tokens.
        JWTAuthentication().get_user(refresh)
        return super().validate(attrs)


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
        fields = ["id", "product", "quantity", "unit_price", "line_total"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    payment_method = serializers.CharField(source="payment.method", read_only=True, default=None)
    payment_status = serializers.CharField(source="payment.status", read_only=True, default=None)
    promo = serializers.CharField(source="promo_code.code", read_only=True, default=None)
    card_brand = serializers.CharField(source="payment.card_brand", read_only=True, default="")
    card_last4 = serializers.CharField(source="payment.card_last4", read_only=True, default="")
    installment_months = serializers.IntegerField(source="payment.installment_months", read_only=True, default=None)

    class Meta:
        model = Order
        fields = ["id", "status", "shipping_address", "total_amount", "discount_amount", "promo",
                  "created_at", "items", "payment_method", "payment_status", "card_brand", "card_last4",
                  "installment_months"]


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = ["id", "kind", "message", "message_ru", "message_kk", "link", "order", "is_read", "created_at"]
