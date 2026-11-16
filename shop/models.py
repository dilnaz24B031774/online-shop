"""
Online Shop - data model (Data & Database: Zhanabergenova Dilnaz)

Every table has a primary key (id, created automatically by PostgreSQL).
Rules that protect data are written as database constraints,
so they work even if somebody forgets to check them in the code.
"""
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.db.models import F, Q
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

    class Currency(models.TextChoices):
        USD = "USD", "US dollar"
        KZT = "KZT", "Kazakhstani tenge"
        EUR = "EUR", "Euro"
        RUB = "RUB", "Russian ruble"

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    preferred_language = models.CharField(
        max_length=2, choices=Language.choices, default=Language.EN
    )
    preferred_currency = models.CharField(
        max_length=3, choices=Currency.choices, default=Currency.USD
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
            models.CheckConstraint(
                condition=Q(preferred_currency__in=["USD", "KZT", "EUR", "RUB"]),
                name="user_currency_valid",
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
class PromoCode(models.Model):
    """Discount code, e.g. BLACKFRIDAY = 20 % off. Checked in services.check_promo()."""
    code = models.CharField(max_length=30, unique=True)          # stored in UPPER case
    discount_percent = models.PositiveSmallIntegerField()        # 1..90
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    max_uses = models.PositiveIntegerField(null=True, blank=True)  # empty = no limit
    used_count = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "promo_codes"
        ordering = ["code"]
        verbose_name = "промокод"
        verbose_name_plural = "промокоды"
        constraints = [
            models.CheckConstraint(condition=Q(discount_percent__gte=1, discount_percent__lte=90),
                                   name="promo_discount_1_90"),
            models.CheckConstraint(condition=Q(min_order_amount__gte=0), name="promo_min_order_not_negative"),
            models.CheckConstraint(condition=Q(max_uses__isnull=True) | Q(used_count__lte=F("max_uses")),
                                   name="promo_used_not_over_limit"),
            models.CheckConstraint(condition=Q(valid_from__isnull=True) | Q(valid_until__isnull=True)
                                   | Q(valid_until__gt=F("valid_from")), name="promo_dates_order"),
        ]

    def save(self, *args, **kwargs):
        self.code = self.code.strip().upper()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.code} (-{self.discount_percent}%)"


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
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)   # after discount
    promo_code = models.ForeignKey(PromoCode, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="orders")
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
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
            models.CheckConstraint(condition=Q(discount_amount__gte=0), name="order_discount_not_negative"),
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
        QR = "qr", "QR in a bank app"
        INSTALLMENT = "installment", "Installment 0-0-12"

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
    # card payments: only the type and the last 4 digits - never the full number or CVC
    card_brand = models.CharField(max_length=12, blank=True)
    card_last4 = models.CharField(max_length=4, blank=True)
    failure_reason = models.CharField(max_length=120, blank=True)
    installment_months = models.PositiveSmallIntegerField(null=True, blank=True)   # 3, 6, 12 or 24

    class Meta:
        db_table = "payments"
        constraints = [
            models.CheckConstraint(condition=Q(amount__gt=0), name="payment_amount_positive"),
            models.CheckConstraint(
                condition=Q(method__in=["card", "bank_transfer", "cash_on_delivery", "qr", "installment"]),
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
            models.CheckConstraint(
                condition=Q(card_last4="") | Q(card_last4__regex=r"^[0-9]{4}$"),
                name="payment_card_last4_digits",
            ),
            # card details only for card payments
            models.CheckConstraint(
                condition=Q(method="card") | (Q(card_last4="") & Q(card_brand="")),
                name="payment_card_only_for_card",
            ),
            # installment: months only for installment payments, and only 3 / 6 / 12 / 24
            models.CheckConstraint(
                condition=(Q(method="installment") & Q(installment_months__in=[3, 6, 12, 24]))
                | (~Q(method="installment") & Q(installment_months__isnull=True)),
                name="payment_installment_months_valid",
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
    class Kind(models.TextChoices):
        ORDER = "order", "Order"            # order paid, cancelled ...
        PROMO = "promo", "Promotion"        # Black Friday and other campaigns
        SYSTEM = "system", "System"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications")
    order = models.ForeignKey(Order, on_delete=models.SET_NULL, null=True, blank=True)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.ORDER)
    message = models.CharField(max_length=255)                 # English (always filled)
    message_ru = models.CharField(max_length=255, blank=True)
    message_kk = models.CharField(max_length=255, blank=True)
    link = models.CharField(max_length=200, blank=True)        # page on the website, e.g. /catalog
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["user", "is_read"], name="notification_user_unread_idx")]
        constraints = [
            models.CheckConstraint(condition=Q(kind__in=["order", "promo", "system"]),
                                   name="notification_kind_valid"),
        ]


class LoginSecurityState(models.Model):
    """Expiring counters; the key is an HMAC, never an account name or IP."""

    key = models.CharField(max_length=64, primary_key=True)
    scope = models.CharField(max_length=20)
    attempts = models.PositiveIntegerField(default=0)
    window_started_at = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True, db_index=True)

    class Meta:
        db_table = "login_security_state"
        verbose_name = "защита входа"
        verbose_name_plural = "защита входа"


class LoginChallenge(models.Model):
    """A short-lived, single-use answer digest bound to one source and purpose."""

    id = models.CharField(max_length=64, primary_key=True)
    source_key = models.CharField(max_length=64)
    purpose = models.CharField(max_length=20)
    answer_digest = models.CharField(max_length=64)
    expires_at = models.DateTimeField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "login_challenges"


class Complaint(models.Model):
    """Private customer complaints and the shop's response."""

    class Category(models.TextChoices):
        PRODUCT = "product", "Товар"
        DELIVERY = "delivery", "Доставка"
        PAYMENT = "payment", "Оплата"
        SERVICE = "service", "Обслуживание"
        OTHER = "other", "Другое"

    class Status(models.TextChoices):
        NEW = "new", "Новое"
        IN_PROGRESS = "in_progress", "В работе"
        RESOLVED = "resolved", "Решено"

    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name="complaints")
    order = models.ForeignKey(
        Order, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaints",
    )
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    subject = models.CharField(max_length=150)
    message = models.TextField(max_length=5000)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    staff_response = models.TextField(max_length=5000, blank=True, default="")
    responded_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name="complaint_responses",
    )
    replied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "complaints"
        ordering = ["-created_at", "-pk"]
        verbose_name = "обращение покупателя"
        verbose_name_plural = "книга жалоб"
        constraints = [
            models.CheckConstraint(
                condition=Q(category__in=["product", "delivery", "payment", "service", "other"]),
                name="complaint_category_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["new", "in_progress", "resolved"]),
                name="complaint_status_valid",
            ),
        ]

    def __str__(self):
        return f"#{self.pk} {self.subject}"
