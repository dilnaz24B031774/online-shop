"""Shop management with historical order and payment data kept intact."""
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    Address, CartItem, Category, City, Complaint, Favorite, Notification, Order, OrderItem, Payment, Product,
    ProductImage, PromoCode, PromoRedemption, Refund, Review, ReviewPhoto, SavedCard, StockSubscription, User,
)
from .roles import MANAGER_GROUP, ROLE_CHOICES, sync_role_access

admin.site.site_header = "SaudaGo · Управление магазином"
admin.site.site_title = "SaudaGo · Администратор"
admin.site.index_title = "Все разделы магазина"
admin.site.site_url = "/staff/"

ROLE_HELP = (
    "Покупатель: без доступа к панели; группы и дополнительные права удаляются. "
    "Менеджер: каталог, заказы и отзывы; при смене роли старые дополнительные права удаляются. "
    "Администратор: полный доступ, включая пользователей и права."
)


class ShopUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = "__all__"
        labels = {"phone": "Телефон", "role": "Роль", "preferred_language": "Язык"}
        help_texts = {"role": ROLE_HELP}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "role" in self.fields:
            self.fields["role"].choices = ROLE_CHOICES


class ShopUserCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name", "phone", "role", "preferred_language")
        labels = ShopUserChangeForm.Meta.labels
        help_texts = {"role": ROLE_HELP}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if "role" in self.fields:
            self.fields["role"].choices = ROLE_CHOICES


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = ShopUserChangeForm
    add_form = ShopUserCreationForm
    list_display = ("username", "email", "role", "preferred_language", "is_active", "is_staff")
    list_filter = ("role", "is_active", "preferred_language")
    search_fields = ("username", "email", "first_name", "last_name", "phone")
    list_per_page = 25
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Личные данные", {"fields": ("first_name", "last_name", "email", "phone", "preferred_language")}),
        ("Доступ к магазину", {"fields": ("role", "is_active", "groups", "user_permissions")}),
        ("Активность", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        ("Новый пользователь", {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2", "first_name", "last_name",
                       "phone", "preferred_language", "role"),
        }),
    )
    readonly_fields = ("last_login", "date_joined")
    actions = ["send_black_friday"]

    @staticmethod
    def _protected_user(obj):
        return obj is not None and (obj.is_staff or obj.is_superuser or obj.role != User.Role.CUSTOMER)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not request.user.is_superuser:
            queryset = queryset.filter(is_staff=False, is_superuser=False, role=User.Role.CUSTOMER)
        return queryset

    def has_view_permission(self, request, obj=None):
        return (request.user.is_superuser or not self._protected_user(obj)) and super().has_view_permission(request, obj)

    def has_change_permission(self, request, obj=None):
        return (request.user.is_superuser or not self._protected_user(obj)) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj is not None and obj.pk == request.user.pk:
            return False
        return (request.user.is_superuser or not self._protected_user(obj)) and super().has_delete_permission(request, obj)

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets
        # Hiding only is_staff/is_superuser is insufficient: groups and permissions
        # can grant equivalent access. Employee accounts are also excluded above.
        privileged = {"role", "groups", "user_permissions", "is_staff", "is_superuser"}
        return tuple(
            (name, {**options, "fields": tuple(field for field in options["fields"] if field not in privileged)})
            for name, options in fieldsets
        )

    def get_form(self, request, obj=None, **kwargs):
        base_form = super().get_form(request, obj, **kwargs)
        if obj is None or obj.pk != request.user.pk or not request.user.is_superuser:
            return base_form

        class OwnAccountForm(base_form):
            def clean(self):
                cleaned = super().clean()
                if cleaned.get("role", obj.role) != User.Role.ADMIN:
                    self.add_error("role", "Нельзя убрать у себя права администратора. Измените роль через другого администратора.")
                if not cleaned.get("is_active", obj.is_active):
                    self.add_error("is_active", "Нельзя отключить собственную учётную запись.")
                return cleaned

        return OwnAccountForm

    def save_model(self, request, obj, form, change):
        obj._sauda_previous_role = (
            User.objects.filter(pk=obj.pk).values_list("role", flat=True).first() if change else None
        )
        if not request.user.is_superuser:
            if self._protected_user(obj):
                raise PermissionDenied
            obj.role = User.Role.CUSTOMER
            obj.is_staff = False
            obj.is_superuser = False
        else:
            obj.is_staff = obj.role in (User.Role.MANAGER, User.Role.ADMIN)
            obj.is_superuser = obj.role == User.Role.ADMIN
        super().save_model(request, obj, form, change)

    @admin.action(description="Отправить уведомление Black Friday выбранным пользователям")
    def send_black_friday(self, request, queryset):
        from .services import send_black_friday
        n = send_black_friday(users=queryset.filter(is_active=True))
        self.message_user(request, f"Уведомление Black Friday отправлено: {n}.", messages.SUCCESS)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        user = form.instance
        sync_role_access(user, previous_role=getattr(user, "_sauda_previous_role", None))


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ru", "name_kk", "product_count", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name_en", "name_ru", "name_kk")
    list_editable = ("is_active",)
    list_per_page = 25

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(_product_count=Count("products"))

    @admin.display(description="Товаров", ordering="_product_count")
    def product_count(self, obj):
        return obj._product_count


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 1
    fields = ("position", "url")
    verbose_name = "Дополнительное фото"
    verbose_name_plural = "Галерея фото"


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    inlines = [ProductImageInline]
    list_display = ("sku", "name_en", "brand", "category", "price", "stock_quantity", "is_active")
    list_filter = ("category", "is_active", "brand")
    search_fields = ("sku", "name_en", "name_ru", "name_kk", "brand")
    list_editable = ("price", "stock_quantity", "is_active")
    list_select_related = ("category",)
    list_per_page = 25
    readonly_fields = ("created_at", "updated_at")
    fieldsets = (
        ("Товар и остатки", {"fields": ("sku", "category", "brand", "price", "stock_quantity", "is_active")}),
        ("Фотография", {"fields": ("image_url",)}),
        ("English", {"fields": ("name_en", "description_en")}),
        ("Русский", {"fields": ("name_ru", "description_ru")}),
        ("Қазақша", {"fields": ("name_kk", "description_kk")}),
        ("Даты", {"fields": ("created_at", "updated_at"), "classes": ("collapse",)}),
    )


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    fields = ("product", "quantity", "unit_price", "line_total")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    @admin.display(description="Сумма")
    def line_total(self, obj):
        return obj.line_total


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "is_demo", "created_at", "process_order")
    list_filter = ("status", "is_demo", "created_at")
    search_fields = ("=id", "user__username", "user__email", "shipping_address")
    list_select_related = ("user",)
    date_hierarchy = "created_at"
    list_per_page = 25
    inlines = [OrderItemInline]
    actions = ["cancel_and_refund"]
    fields = ("process_order", "user", "status", "shipping_address", "promo_code", "discount_amount",
              "total_amount", "created_at", "updated_at")
    readonly_fields = fields

    @admin.display(description="Обработка")
    def process_order(self, obj):
        return format_html('<a href="{}">Открыть заказ в панели</a>', reverse("staff_order_detail", args=[obj.pk]))

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Отменить заказы и вернуть оплату и товары на склад", permissions=["change"])
    def cancel_and_refund(self, request, queryset):
        from .services import CancelNotAllowedError, cancel_order
        done = 0
        for order in queryset:
            try:
                cancel_order(order, by_staff=True)
                done += 1
            except CancelNotAllowedError as error:
                self.message_user(request, str(error), messages.WARNING)
        if done:
            self.message_user(request, f"Отменено заказов: {done}. Оплата и склад обновлены.", messages.SUCCESS)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "amount", "status", "refunded_amount", "expires_at", "paid_at")
    list_filter = ("status", "method", "paid_at")
    search_fields = ("=order__id", "order__user__username", "provider_reference")
    list_select_related = ("order",)
    readonly_fields = ("order", "method", "amount", "status", "provider_reference", "paid_at", "card_brand",
                       "card_last4", "saved_card", "expires_at", "refunded_amount", "failure_reason")
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("user", "label", "city", "street", "is_default")
    list_filter = ("city", "is_default")
    search_fields = ("user__username", "city", "street", "postal_code")
    list_select_related = ("user",)
    raw_id_fields = ("user",)


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "quantity", "added_at")
    search_fields = ("user__username", "product__sku", "product__name_en", "product__name_ru")
    list_select_related = ("user", "product")
    readonly_fields = ("added_at",)
    raw_id_fields = ("user", "product")


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "order_item", "rating", "comment", "created_at")
    list_filter = ("rating", "created_at")
    search_fields = ("user__username", "product__name_en", "product__name_ru", "comment")
    list_select_related = ("user", "product", "order_item__order")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user", "product", "order_item")

    def get_readonly_fields(self, request, obj=None):
        return ("user", "product", "order_item", "created_at") if obj else ("created_at",)


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "kind", "order", "message", "is_read", "created_at")
    list_filter = ("kind", "is_read", "created_at")
    search_fields = ("user__username", "message", "=order__id")
    list_select_related = ("user", "order")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user", "order")


@admin.register(PromoCode)
class PromoCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "discount_percent", "min_order_amount", "valid_from", "valid_until",
                    "used_count", "max_uses", "is_active")
    list_filter = ("is_active",)
    list_editable = ("is_active",)
    search_fields = ("code",)
    readonly_fields = ("used_count", "created_at")


@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    """The staff inbox is the only write path, preserving response validation."""

    list_display = ("id", "subject", "user", "category", "status", "created_at", "process_complaint")
    list_filter = ("status", "category", "created_at")
    search_fields = ("subject", "message", "user__username")
    list_select_related = ("user", "order", "responded_by")
    list_per_page = 25
    actions = None
    fields = (
        "process_complaint", "user", "order", "category", "subject", "message", "status",
        "staff_response", "responded_by", "replied_at", "created_at", "updated_at",
    )
    readonly_fields = fields

    @admin.display(description="Обработка")
    def process_complaint(self, obj):
        return format_html(
            '<a href="{}">Открыть обращение в панели</a>',
            reverse("staff_complaint_detail", args=[obj.pk]),
        )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Favorite)
class FavoriteAdmin(admin.ModelAdmin):
    list_display = ("user", "product", "created_at")
    search_fields = ("user__username", "product__name_en", "product__name_ru", "product__sku")
    list_select_related = ("user", "product")
    readonly_fields = ("created_at",)
    raw_id_fields = ("user", "product")


class ReadOnlyAdmin(admin.ModelAdmin):
    """History tables: rows are written only by the shop logic, nobody edits them by hand."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Refund)
class RefundAdmin(ReadOnlyAdmin):
    list_display = ("created_at", "order", "order_item", "quantity", "amount", "reason", "created_by")
    list_filter = ("reason", "created_at")
    search_fields = ("=order__id", "order__user__username")


@admin.register(SavedCard)
class SavedCardAdmin(ReadOnlyAdmin):
    list_display = ("user", "brand", "last4", "exp_month", "exp_year", "last_used_at")
    search_fields = ("user__username", "last4")
    exclude = ("token",)          # the token is secret even for the staff


@admin.register(StockSubscription)
class StockSubscriptionAdmin(ReadOnlyAdmin):
    list_display = ("product", "user", "created_at", "notified_at")
    list_filter = ("notified_at",)
    search_fields = ("product__name_en", "product__name_ru", "user__username")


@admin.register(PromoRedemption)
class PromoRedemptionAdmin(ReadOnlyAdmin):
    list_display = ("promo", "user", "order", "created_at")
    search_fields = ("promo__code", "user__username")


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ("name_ru", "name_en", "delivery_days_min", "delivery_days_max", "sort_order", "is_active")
    list_editable = ("delivery_days_min", "delivery_days_max", "sort_order", "is_active")
    search_fields = ("name_ru", "name_en", "name_kk")


@admin.register(ReviewPhoto)
class ReviewPhotoAdmin(admin.ModelAdmin):
    list_display = ("review", "position", "image", "created_at")
    list_select_related = ("review",)
