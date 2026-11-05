from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (
    Address, CartItem, Category, Notification, Order, OrderItem, Payment, Product, Review, User,
)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("username", "email", "role", "preferred_language", "is_active")
    list_filter = ("role", "is_active", "preferred_language")
    search_fields = ("username", "email", "phone")
    fieldsets = BaseUserAdmin.fieldsets + (
        ("Shop", {"fields": ("phone", "role", "preferred_language")}),
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name_en", "name_ru", "name_kk", "is_active")
    search_fields = ("name_en", "name_ru", "name_kk")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("sku", "name_en", "brand", "category", "price", "stock_quantity", "is_active")
    list_filter = ("category", "is_active")
    search_fields = ("sku", "name_en", "name_ru", "name_kk")
    list_editable = ("price", "stock_quantity", "is_active")


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "total_amount", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "user__username", "shipping_address")
    inlines = [OrderItemInline]
    actions = ["cancel_and_refund"]

    @admin.action(description="Cancel and refund selected orders (stock is returned)")
    def cancel_and_refund(self, request, queryset):
        from .services import CancelNotAllowedError, cancel_order
        done = 0
        for order in queryset:
            try:
                cancel_order(order, by_staff=True)
                done += 1
            except CancelNotAllowedError as e:
                self.message_user(request, str(e), messages.WARNING)
        if done:
            self.message_user(request, f"{done} order(s) cancelled and refunded.", messages.SUCCESS)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "method", "amount", "status", "paid_at")
    list_filter = ("status", "method")


admin.site.register(Address)
admin.site.register(CartItem)
admin.site.register(Review)
admin.site.register(Notification)
