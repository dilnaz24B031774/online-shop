"""
Online Shop - data model (Data & Database: Zhanabergenova Dilnaz)

Every table has a primary key (id, created automatically by PostgreSQL).
Rules that protect data are written as database constraints,
so they work even if somebody forgets to check them in the code.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import Q
from django.utils.translation import get_language


# ---------------------------------------------------------------------
# Helper: one field in three languages (EN is required, RU/KK optional)
# ---------------------------------------------------------------------
class MultiLanguageNameMixin(models.Model):
    name_en = models.CharField(max_length=150)
    name_ru = models.CharField(max_length=150, blank=True)
    name_kk = models.CharField(max_length=150, blank=True)

    class Meta:
        abstract = True

    @property
    def name(self):
        """Name in the current UI language; falls back to English."""
        lang = (get_language() or "en")[:2]
        return getattr(self, f"name_{lang}", "") or self.name_en

    def __str__(self):
        return self.name_en


# ---------------------------------------------------------------------
# 1. USER - customers, managers and admins in one table
# ---------------------------------------------------------------------
class User(AbstractUser):
    """
    Django's user + our fields. The password column stores only a HASH
    (pbkdf2_sha256), never the real password.
    """

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        MANAGER = "manager", "Store manager"
        ADMIN = "admin", "Administrator"

    class Language(models.TextChoices):
        EN = "en", "English"
        RU = "ru", "Русский"
        KK = "kk", "Қазақша"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    preferred_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.EN
    )

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
                condition=Q(role__in=["customer", "manager", "admin"]),
                name="user_role_valid",
            ),
            models.CheckConstraint(
                condition=Q(preferred_language__in=["en", "ru", "kk"]),
                name="user_language_valid",
            ),
        ]


# ---------------------------------------------------------------------
# 2. ADDRESS - one customer can save many addresses
# ---------------------------------------------------------------------
class Address(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=30, default="Home")  # Home, Work ...
    city = models.CharField(max_length=60)
    street = models.CharField(max_length=150)
    apartment = models.CharField(max_length=20, blank=True)
    postal_code = models.CharField(max_length=10, blank=True)
    is_default = models.BooleanField(default=False)

    class Meta:
        db_table = "addresses"
        verbose_name_plural = "addresses"
        constraints = [
            # only ONE default address per user
            models.UniqueConstraint(
                fields=["user"], condition=Q(is_default=True),
                name="address_one_default_per_user",
            ),
        ]

    def full_text(self):
        apt = f", apt {self.apartment}" if self.apartment else ""
        return f"{self.city}, {self.street}{apt}"

    def __str__(self):
        return f"{self.user.username}: {self.label} - {self.full_text()}"


# ---------------------------------------------------------------------
# 3. CATEGORY
# ---------------------------------------------------------------------
class Category(MultiLanguageNameMixin):
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "categories"
        verbose_name_plural = "categories"
        constraints = [
            models.UniqueConstraint(fields=["name_en"], name="category_name_en_unique"),
        ]


# ---------------------------------------------------------------------
# 4. PRODUCT
# ---------------------------------------------------------------------
class Product(MultiLanguageNameMixin):
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    sku = models.CharField(max_length=30, unique=True)  # shop code, e.g. EL-MOUSE-01
    description_en = models.TextField(blank=True)
    description_ru = models.TextField(blank=True)
    description_kk = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock_quantity = models.PositiveIntegerField(default=0)
    brand = models.CharField(max_length=60, blank=True)
    # link to the product photo (can be changed in the admin panel)
    image_url = models.URLField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "products"
        indexes = [
            models.Index(fields=["category", "is_active"], name="product_category_active_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=Q(price__gt=0), name="product_price_positive"),
            models.CheckConstraint(condition=Q(stock_quantity__gte=0), name="product_stock_not_negative"),
        ]


# ---------------------------------------------------------------------
# 5. CART ITEM - products a customer wants to buy (before the order)
# ---------------------------------------------------------------------
class CartItem(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="cart_items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="+")
    quantity = models.PositiveIntegerField(default=1)
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "cart_items"
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="cart_one_row_per_product"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="cart_quantity_positive"),
        ]

    @property
    def line_total(self):
        return self.product.price * self.quantity


# ---------------------------------------------------------------------
# 6. ORDER
# ---------------------------------------------------------------------
class Order(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="orders")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # copied from Address at order time, so old orders keep the old address
    shipping_address = models.CharField(max_length=255)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["status", "created_at"], name="order_status_date_idx")]
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=["pending", "paid", "shipped", "delivered", "cancelled"]),
                name="order_status_valid",
            ),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="order_total_not_negative"),
        ]

    def __str__(self):
        return f"Order #{self.pk} ({self.status})"


# ---------------------------------------------------------------------
# 7. ORDER ITEM - bridge table, solves Order <-> Product M:N
# ---------------------------------------------------------------------
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # price at purchase time

    class Meta:
        db_table = "order_items"
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="order_item_unique_product"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="order_item_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gt=0), name="order_item_price_positive"),
        ]

    @property
    def line_total(self):
        return self.unit_price * self.quantity


# ---------------------------------------------------------------------
# 8. PAYMENT - 1:1 with Order. Card numbers are NEVER stored.
# ---------------------------------------------------------------------
class Payment(models.Model):
    class Method(models.TextChoices):
        CARD = "card", "Card"
        BANK_TRANSFER = "bank_transfer", "Bank transfer"
        CASH = "cash_on_delivery", "Cash on delivery"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="payment")
    method = models.CharField(max_length=20, choices=Method.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    # reference/token from the payment provider instead of card data
    provider_reference = models.CharField(max_length=64, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "payments"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=Q(method__in=["card", "bank_transfer", "cash_on_delivery"]),
                name="payment_method_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["pending", "paid", "failed", "refunded"]),
                name="payment_status_valid",
            ),
            # a paid payment must have a payment time
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(paid_at__isnull=False),
                name="payment_paid_has_time",
            ),
        ]


# ---------------------------------------------------------------------
# 9. REVIEW - one review per customer per product, rating 1..5
# ---------------------------------------------------------------------
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="review_one_per_user_product"),
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
        ]


# ---------------------------------------------------------------------
# 10. NOTIFICATION - messages for the user (order paid, shipped ...)
# ---------------------------------------------------------------------
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    message = models.CharField(max_length=255)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"], name="notification_user_unread_idx")]
