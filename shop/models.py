"""
Online Shop - data model (Data & Database: Zhanabergenova Dilnaz)

Every table has a primary key (id, created automatically by PostgreSQL).
Rules that protect data are written as database constraints,
so they work even if somebody forgets to check them in the code.
"""
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
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
class City(models.Model):
    """Cities we deliver to. The customer picks one after signing in ("Are you from Almaty?")."""
    name_en = models.CharField(max_length=60, unique=True)
    name_ru = models.CharField(max_length=60)
    name_kk = models.CharField(max_length=60)
    delivery_days_min = models.PositiveSmallIntegerField(default=1)
    delivery_days_max = models.PositiveSmallIntegerField(default=3)
    sort_order = models.PositiveSmallIntegerField(default=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "cities"
        ordering = ["sort_order", "name_ru"]
        verbose_name_plural = "cities"
        constraints = [
            models.CheckConstraint(condition=Q(delivery_days_min__gte=1), name="city_days_min_positive"),
            models.CheckConstraint(condition=Q(delivery_days_max__gte=F("delivery_days_min")), name="city_days_max_not_less_min"),
        ]

    def __str__(self):
        return self.name_ru or self.name_en


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
    city = models.ForeignKey("City", on_delete=models.SET_NULL, null=True, blank=True, related_name="users")
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
# Telegram recovery: verified destinations and expiring one-use challenges.
# ---------------------------------------------------------------------
class TelegramAccount(models.Model):
    """A recovery destination verified by a private message to our bot."""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="telegram_account")
    telegram_id = models.PositiveBigIntegerField(unique=True)
    username = models.CharField(max_length=64, blank=True)
    linked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "telegram_accounts"


class TelegramChallenge(models.Model):
    """Only HMACs are stored; raw link nonces and recovery codes are ephemeral."""

    key = models.CharField(max_length=64, primary_key=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True,
                             related_name="telegram_challenges")
    purpose = models.CharField(max_length=8)
    password_digest = models.CharField(max_length=64, blank=True)
    code_digest = models.CharField(max_length=64, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    consumed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "telegram_challenges"
        constraints = [
            models.CheckConstraint(condition=Q(purpose__in=["link", "reset"]), name="telegram_challenge_purpose"),
            models.CheckConstraint(condition=Q(attempts__lte=5), name="telegram_challenge_attempts"),
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


class ProductImage(models.Model):
    """Extra photos of a product (gallery). The main photo stays in products.image_url."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    url = models.URLField(max_length=300)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        db_table = "product_images"
        ordering = ["product", "position"]
        constraints = [
            models.UniqueConstraint(fields=["product", "position"], name="product_image_position_unique"),
            models.UniqueConstraint(fields=["product", "url"], name="product_image_url_unique"),
        ]

    def __str__(self):
        return f"{self.product.sku} #{self.position}"


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
    # demo orders made by "seed_shop" - hits, trends and reports use only REAL orders
    is_demo = models.BooleanField(default=False)
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


class DeliveryTracking(models.Model):
    """Reported courier coordinates; an empty assignment never implies a GPS fix."""

    class Source(models.TextChoices):
        MANUAL = "manual", "Обновлено сотрудником"
        GPS = "gps", "GPS-сервис"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="delivery_tracking")
    courier_name = models.CharField(max_length=120, blank=True)
    courier_phone = models.CharField(max_length=32, blank=True)
    courier_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    courier_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    destination_lat = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-90), MaxValueValidator(90)],
    )
    destination_lng = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        validators=[MinValueValidator(-180), MaxValueValidator(180)],
    )
    eta_minutes = models.PositiveIntegerField(null=True, blank=True)
    source = models.CharField(max_length=10, choices=Source.choices, default=Source.MANUAL)
    position_accuracy = models.FloatField(null=True, blank=True, validators=[MinValueValidator(0)])
    position_updated_at = models.DateTimeField(null=True, blank=True)
    # Raw sharing tokens are shown once and never persisted.
    share_token_hash = models.CharField(max_length=64, null=True, blank=True, unique=True)
    share_expires_at = models.DateTimeField(null=True, blank=True)
    # when the customer was told "the courier is nearby" (once per delivery)
    near_notified_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "delivery_tracking"
        verbose_name = "отслеживание доставки"
        verbose_name_plural = "отслеживание доставок"
        constraints = [
            models.CheckConstraint(
                condition=(Q(courier_lat__isnull=True, courier_lng__isnull=True)
                           | Q(courier_lat__isnull=False, courier_lng__isnull=False)),
                name="delivery_courier_coordinates_paired",
            ),
            models.CheckConstraint(
                condition=(Q(destination_lat__isnull=True, destination_lng__isnull=True)
                           | Q(destination_lat__isnull=False, destination_lng__isnull=False)),
                name="delivery_destination_coordinates_paired",
            ),
            models.CheckConstraint(
                condition=Q(courier_lat__isnull=True) | Q(courier_lat__gte=-90, courier_lat__lte=90),
                name="delivery_courier_latitude_valid",
            ),
            models.CheckConstraint(
                condition=Q(courier_lng__isnull=True) | Q(courier_lng__gte=-180, courier_lng__lte=180),
                name="delivery_courier_longitude_valid",
            ),
            models.CheckConstraint(
                condition=Q(destination_lat__isnull=True) | Q(destination_lat__gte=-90, destination_lat__lte=90),
                name="delivery_destination_latitude_valid",
            ),
            models.CheckConstraint(
                condition=Q(destination_lng__isnull=True) | Q(destination_lng__gte=-180, destination_lng__lte=180),
                name="delivery_destination_longitude_valid",
            ),
            models.CheckConstraint(
                condition=(~Q(courier_name="") | Q(courier_phone="", courier_lat__isnull=True,
                                                   courier_lng__isnull=True, eta_minutes__isnull=True)),
                name="delivery_position_requires_assignment",
            ),
            models.CheckConstraint(condition=Q(source__in=["manual", "gps"]), name="delivery_source_valid"),
            models.CheckConstraint(
                condition=Q(position_accuracy__isnull=True) | Q(position_accuracy__gte=0),
                name="delivery_accuracy_nonnegative",
            ),
            models.CheckConstraint(
                condition=(Q(share_token_hash__isnull=True, share_expires_at__isnull=True)
                           | Q(share_token_hash__isnull=False, share_expires_at__isnull=False)),
                name="delivery_share_expiry_paired",
            ),
        ]

    def clean(self):
        super().clean()
        self.courier_name = self.courier_name.strip()
        self.courier_phone = self.courier_phone.strip()
        errors = {}
        for prefix in ("courier", "destination"):
            lat, lng = getattr(self, f"{prefix}_lat"), getattr(self, f"{prefix}_lng")
            if (lat is None) != (lng is None):
                errors[f"{prefix}_lat"] = "Укажите широту и долготу вместе или очистите оба поля."
        if not self.courier_name and (
            self.courier_phone or self.courier_lat is not None or self.courier_lng is not None
            or self.eta_minutes is not None
        ):
            errors["courier_name"] = "Сначала укажите имя назначенного курьера."
        if self.courier_phone:
            import re
            digits = re.sub(r"[^0-9]", "", self.courier_phone)
            if not re.fullmatch(r"\+?[0-9 ()-]+", self.courier_phone) or not 7 <= len(digits) <= 15:
                errors["courier_phone"] = "Укажите телефон: от 7 до 15 цифр."
            else:
                self.courier_phone = ("+" if self.courier_phone.startswith("+") else "") + digits
        if self.position_accuracy is not None:
            import math
            if not math.isfinite(self.position_accuracy):
                errors["position_accuracy"] = "Точность должна быть конечным числом."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Доставка заказа №{self.order_id}"


# ---------------------------------------------------------------------
# 7. ORDER ITEM - bridge table, solves Order <-> Product M:N
# ---------------------------------------------------------------------
class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)  # price at purchase time
    refunded_quantity = models.PositiveIntegerField(default=0)         # how many were returned

    class Meta:
        db_table = "order_items"
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="order_item_unique_product"),
            models.CheckConstraint(condition=Q(quantity__gt=0), name="order_item_quantity_positive"),
            models.CheckConstraint(condition=Q(unit_price__gt=0), name="order_item_price_positive"),
            # you cannot return more than you bought
            models.CheckConstraint(condition=Q(refunded_quantity__lte=F("quantity")),
                                   name="order_item_refund_not_over_quantity"),
        ]

    @property
    def line_total(self):
        return self.unit_price * self.quantity

    @property
    def refundable_quantity(self):
        return self.quantity - self.refunded_quantity


# ---------------------------------------------------------------------
# 7b. SAVED CARD - a TOKEN instead of the card number (only type + last 4 digits)
# ---------------------------------------------------------------------
class SavedCard(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_cards")
    token = models.CharField(max_length=40, unique=True)          # tok_... from the (demo) bank
    brand = models.CharField(max_length=12)
    last4 = models.CharField(max_length=4)
    holder = models.CharField(max_length=60)
    exp_month = models.PositiveSmallIntegerField()
    exp_year = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_used_at = models.DateTimeField()

    class Meta:
        db_table = "saved_cards"
        ordering = ["-last_used_at"]
        constraints = [
            models.CheckConstraint(condition=Q(last4__regex=r"^[0-9]{4}$"), name="saved_card_last4_digits"),
            models.CheckConstraint(condition=Q(exp_month__gte=1, exp_month__lte=12), name="saved_card_month_1_12"),
            models.UniqueConstraint(fields=["user", "brand", "last4", "exp_month", "exp_year"],
                                    name="saved_card_once_per_user"),
        ]

    def __str__(self):
        return f"{self.brand.upper()} •••• {self.last4} ({self.user.username})"


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
    saved_card = models.ForeignKey(SavedCard, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name="payments")
    # QR / bank transfer: after this moment an unpaid order is cancelled automatically
    expires_at = models.DateTimeField(null=True, blank=True)
    refunded_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

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
            # money back: never negative and never more than was paid
            models.CheckConstraint(condition=Q(refunded_amount__gte=0) & Q(refunded_amount__lte=F("amount")),
                                   name="payment_refund_not_over_amount"),
        ]


# ---------------------------------------------------------------------
# 9. REVIEW - one review per purchased order line, rating 1..5
# ---------------------------------------------------------------------
class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reviews")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reviews")
    # Null is reserved for historical reviews whose purchase cannot be proven.
    # All new customer reviews are attached to an owned, paid purchase.
    order_item = models.OneToOneField(
        OrderItem, on_delete=models.PROTECT, related_name="review", null=True, blank=True,
    )
    rating = models.PositiveSmallIntegerField()
    comment = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reviews"
        constraints = [
            models.CheckConstraint(condition=Q(rating__gte=1, rating__lte=5), name="review_rating_1_to_5"),
        ]

    def clean(self):
        super().clean()
        previous = type(self).objects.filter(pk=self.pk).first() if self.pk else None
        if previous and (previous.user_id, previous.product_id, previous.order_item_id) != (
            self.user_id, self.product_id, self.order_item_id,
        ):
            raise ValidationError("A published review's author, product and purchase cannot be changed.")
        if not self.order_item_id:
            if previous is None:
                raise ValidationError({"order_item": "Choose a paid purchase for this review."})
            return
        item = self.order_item
        errors = {}
        if item.order.user_id != self.user_id:
            errors["user"] = "This purchase belongs to another customer."
        if item.product_id != self.product_id:
            errors["product"] = "Choose the product from this purchase."
        # A later refund must not prevent moderation of an existing review.
        if previous is None and (
            item.order.status not in (Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED)
            or not Payment.objects.filter(order_id=item.order_id, status=Payment.Status.PAID).exists()
        ):
            errors["order_item"] = "Reviews are available only after a paid purchase."
        if errors:
            raise ValidationError(errors)


REVIEW_PHOTOS_MAX = 3


class ReviewPhoto(models.Model):
    """Up to 3 photos in a review. The file is on disk (media/reviews/...), the table keeps its path."""
    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="photos")
    image = models.FileField(upload_to="reviews/%Y/%m/")
    position = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "review_photos"
        ordering = ["review", "position"]
        constraints = [
            models.UniqueConstraint(fields=["review", "position"], name="review_photo_position_unique"),
            # positions 0, 1, 2 only -> the database itself allows at most 3 photos per review
            models.CheckConstraint(condition=Q(position__lt=REVIEW_PHOTOS_MAX), name="review_photo_max_3"),
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


# ---------------------------------------------------------------------
# 11. FAVORITE - liked products of a customer
# ---------------------------------------------------------------------
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="favorites")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="favorited_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "favorites"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "product"], name="favorite_one_per_user_product"),
        ]


# ---------------------------------------------------------------------
# 12. REFUND - money back for some items of a paid order (one row per return)
# ---------------------------------------------------------------------
class Refund(models.Model):
    class Reason(models.TextChoices):
        DEFECT = "defect", "Defective item"
        WRONG_ITEM = "wrong_item", "Wrong item"
        CHANGED_MIND = "changed_mind", "Customer changed mind"
        OTHER = "other", "Other"

    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="refunds")
    order_item = models.ForeignKey(OrderItem, on_delete=models.PROTECT, related_name="refunds")
    quantity = models.PositiveIntegerField()
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.OTHER)
    comment = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "refunds"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="refund_quantity_positive"),
            models.CheckConstraint(condition=Q(amount__gt=0), name="refund_amount_positive"),
            models.CheckConstraint(condition=Q(reason__in=["defect", "wrong_item", "changed_mind", "other"]),
                                   name="refund_reason_valid"),
        ]


# ---------------------------------------------------------------------
# 13. STOCK SUBSCRIPTION - "tell me when it is back in stock"
# ---------------------------------------------------------------------
class StockSubscription(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="stock_subscriptions")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_subscriptions")
    created_at = models.DateTimeField(auto_now_add=True)
    notified_at = models.DateTimeField(null=True, blank=True)     # filled when the product came back

    class Meta:
        db_table = "stock_subscriptions"
        constraints = [
            # only one ACTIVE subscription per customer and product
            models.UniqueConstraint(fields=["user", "product"], condition=Q(notified_at__isnull=True),
                                    name="stock_subscription_one_active"),
        ]


# ---------------------------------------------------------------------
# 14. PROMO REDEMPTION - each customer can use a promo code only ONCE
# ---------------------------------------------------------------------
class PromoRedemption(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="promo_redemptions")
    promo = models.ForeignKey(PromoCode, on_delete=models.CASCADE, related_name="redemptions")
    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="promo_redemption")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "promo_redemptions"
        constraints = [
            models.UniqueConstraint(fields=["user", "promo"], name="promo_once_per_user"),
        ]


# ---------------------------------------------------------------------
# 15. QR PAYMENT - a one-time secret link inside the QR code (scanned with a phone)
# ---------------------------------------------------------------------
class QrPayment(models.Model):
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, related_name="qr")
    token = models.CharField(max_length=64, unique=True)          # random, impossible to guess
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()                           # the same moment as the payment timer
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_device = models.CharField(max_length=80, blank=True)     # e.g. "iPhone · Safari"

    class Meta:
        db_table = "qr_payments"
        constraints = [
            models.CheckConstraint(condition=Q(expires_at__gt=F("created_at")), name="qr_expires_after_created"),
            # a QR is paid only once and only with a device written down
            models.CheckConstraint(condition=Q(paid_at__isnull=True) | ~Q(paid_device=""), name="qr_paid_has_device"),
        ]

    def __str__(self):
        return f"QR for order #{self.payment.order_id}"


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


# ---------- bonus programme: treat the mascots, collect merch ----------

class BonusFeeding(models.Model):
    """The customer gave earned treats (kurt / Nauryz kozhe) to one of the two mascots."""
    class Character(models.TextChoices):
        AISULU = "aisulu", "Айсұлу"
        ALTAI = "altai", "Алтай"

    class Treat(models.TextChoices):
        KURT = "kurt", "Құрт"
        KOZHE = "kozhe", "Наурыз көже"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="bonus_feedings")
    character = models.CharField(max_length=10, choices=Character.choices)
    treat = models.CharField(max_length=10, choices=Treat.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "bonus_feedings"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=Q(character__in=["aisulu", "altai"]), name="bonus_character_valid"),
            models.CheckConstraint(condition=Q(treat__in=["kurt", "kozhe"]), name="bonus_treat_valid"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="bonus_quantity_positive"),
        ]


class GiftClaim(models.Model):
    """A merch gift the customer unlocked and asked for; staff send it out."""
    class Status(models.TextChoices):
        REQUESTED = "requested", "Ждёт отправки"
        SENT = "sent", "Отправлен"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="gift_claims")
    gift = models.CharField(max_length=40)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.REQUESTED)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "gift_claims"
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["user", "gift"], name="gift_claim_once_per_user"),
            models.CheckConstraint(condition=Q(status__in=["requested", "sent"]), name="gift_claim_status_valid"),
        ]
