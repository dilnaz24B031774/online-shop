"""Session-authenticated shop management; Django permissions protect every action."""
from decimal import Decimal

from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Count, ProtectedError, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods, require_safe

from .models import Category, Order, Product, User
from .roles import ROLE_CHOICES
from .services import (
    STAFF_CAN_CANCEL, CancelNotAllowedError, OrderTransitionError, cancel_order,
    confirm_payment, fulfill_order,
)


STATUS_CHOICES = (
    (Order.Status.PENDING, "Ожидает оплаты"),
    (Order.Status.PAID, "Оплачен"),
    (Order.Status.SHIPPED, "Отправлен"),
    (Order.Status.DELIVERED, "Доставлен"),
    (Order.Status.CANCELLED, "Отменён"),
)


def _can_view(user, model):
    return any(user.has_perm(f"shop.{action}_{model}") for action in ("view", "change"))


def _require_view(request, model):
    if not _can_view(request.user, model):
        raise PermissionDenied


def _page(request, queryset):
    return Paginator(queryset, 20).get_page(request.GET.get("page"))


def _name_search(q):
    return Q(name_en__icontains=q) | Q(name_ru__icontains=q) | Q(name_kk__icontains=q)


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name_en", "sku", "category", "price", "stock_quantity", "is_active",
            "brand", "image_url", "description_en", "name_ru", "description_ru",
            "name_kk", "description_kk",
        )
        labels = {
            "name_en": "Название (EN)", "sku": "Артикул (SKU)",
            "category": "Категория", "price": "Цена, $",
            "stock_quantity": "Остаток", "is_active": "Показывать на витрине",
            "brand": "Бренд", "image_url": "Ссылка на фото", "description_en": "Описание (EN)",
            "name_ru": "Название (RU)", "description_ru": "Описание (RU)",
            "name_kk": "Название (KK)", "description_kk": "Описание (KK)",
        }
        widgets = {field: forms.Textarea(attrs={"rows": 4}) for field in (
            "description_en", "description_ru", "description_kk",
        )}


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ("name_en", "name_ru", "name_kk", "is_active")
        labels = {
            "name_en": "Название (EN)", "name_ru": "Название (RU)",
            "name_kk": "Название (KK)", "is_active": "Показывать на витрине",
        }


@require_safe
def dashboard(request):
    visibility = {model: _can_view(request.user, model) for model in (
        "product", "category", "order", "user",
    )}
    if not any(visibility.values()):
        raise PermissionDenied
    stats = dict.fromkeys((
        "products", "categories", "orders", "customers", "revenue", "pending_orders", "low_stock",
    ))
    low_stock_products = Product.objects.none()
    recent_orders = Order.objects.none()
    if visibility["product"]:
        low_stock_products = Product.objects.filter(
            is_active=True, stock_quantity__lte=5,
        ).select_related("category").order_by("stock_quantity", "name_en", "pk")
        stats.update(products=Product.objects.count(), low_stock=low_stock_products.count())
    if visibility["category"]:
        stats["categories"] = Category.objects.count()
    if visibility["user"]:
        stats["customers"] = User.objects.filter(role=User.Role.CUSTOMER).count()
    if visibility["order"]:
        orders_qs = Order.objects.all()
        stats.update(
            orders=orders_qs.count(),
            pending_orders=orders_qs.filter(status__in=(Order.Status.PENDING, Order.Status.PAID)).count(),
            revenue=orders_qs.filter(status__in=(
                Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED,
            )).aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00"),
        )
        recent_orders = orders_qs.select_related("user").order_by("-created_at", "-pk")[:6]
    return render(request, "shop/staff_dashboard.html", {
        "stats": stats, "recent_orders": recent_orders,
        "low_stock_products": low_stock_products[:6], "active_section": "dashboard",
    })


@require_safe
def catalog(request):
    _require_view(request, "product")
    q = request.GET.get("q", "").strip()
    category_filter = request.GET.get("category", "")
    active_filter = request.GET.get("active", "")
    stock_filter = request.GET.get("stock", "")
    products = Product.objects.select_related("category").order_by("name_en", "pk")
    if q:
        products = products.filter(_name_search(q) | Q(sku__icontains=q) | Q(brand__icontains=q))
    if category_filter.isdecimal() and len(category_filter) < 19:
        products = products.filter(category_id=int(category_filter))
    else:
        category_filter = ""
    if active_filter in ("yes", "no"):
        products = products.filter(is_active=active_filter == "yes")
    else:
        active_filter = ""
    if stock_filter == "low":
        products = products.filter(stock_quantity__lte=5)
    else:
        stock_filter = ""
    return render(request, "shop/staff_catalog.html", {
        "page_obj": _page(request, products), "categories": Category.objects.order_by("name_en"),
        "q": q, "category_filter": category_filter, "active_filter": active_filter,
        "stock_filter": stock_filter, "active_section": "catalog",
    })


def _object_form(request, model, form_class, section, list_name, add_name, pk):
    permission = "add" if pk is None else "change"
    if not request.user.has_perm(f"shop.{permission}_{model._meta.model_name}"):
        raise PermissionDenied
    obj = None if pk is None else get_object_or_404(model, pk=pk)
    form = form_class(request.POST if request.method == "POST" else None, instance=obj)
    noun = "товар" if model is Product else "категорию"
    title = f"{'Добавить' if obj is None else 'Редактировать'} {noun}"
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Изменения сохранены.")
        return redirect(list_name if _can_view(request.user, model._meta.model_name) else add_name)
    return render(request, "shop/staff_form.html", {
        "form": form, "object": obj, "title": title,
        "back_url": reverse(list_name), "submit_label": "Сохранить изменения",
        "active_section": section,
    })


@require_http_methods(["GET", "HEAD", "POST"])
def product_form(request, pk=None):
    return _object_form(request, Product, ProductForm, "catalog", "staff_catalog", "staff_product_add", pk)


def _object_delete(request, model, section, list_name, pk):
    if not request.user.has_perm(f"shop.delete_{model._meta.model_name}"):
        raise PermissionDenied
    obj = get_object_or_404(model, pk=pk)
    error = ""
    if request.method == "POST":
        try:
            obj.delete()
        except ProtectedError:
            error = (
                "Удаление невозможно: запись используется в заказах или товарах. "
                "Откройте редактирование и снимите отметку «Показывать на витрине»."
            )
        else:
            messages.success(request, "Запись удалена.")
            return redirect(list_name)
    return render(request, "shop/staff_confirm_delete.html", {
        "object": obj, "title": "Удалить товар" if model is Product else "Удалить категорию",
        "back_url": reverse(list_name), "error": error, "active_section": section,
    })


@require_http_methods(["GET", "HEAD", "POST"])
def product_delete(request, pk):
    return _object_delete(request, Product, "catalog", "staff_catalog", pk)


@require_safe
def categories(request):
    _require_view(request, "category")
    q = request.GET.get("q", "").strip()
    queryset = Category.objects.annotate(product_count=Count("products")).order_by("name_en", "pk")
    if q:
        queryset = queryset.filter(_name_search(q))
    return render(request, "shop/staff_categories.html", {
        "page_obj": _page(request, queryset), "q": q, "active_section": "categories",
    })


@require_http_methods(["GET", "HEAD", "POST"])
def category_form(request, pk=None):
    return _object_form(request, Category, CategoryForm, "categories", "staff_categories", "staff_category_add", pk)


@require_http_methods(["GET", "HEAD", "POST"])
def category_delete(request, pk):
    return _object_delete(request, Category, "categories", "staff_categories", pk)


@require_safe
def orders(request):
    _require_view(request, "order")
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    queryset = Order.objects.select_related("user", "payment").order_by("-created_at", "-pk")
    if q:
        search = (
            Q(user__username__icontains=q) | Q(user__email__icontains=q) |
            Q(user__first_name__icontains=q) | Q(user__last_name__icontains=q) |
            Q(shipping_address__icontains=q)
        )
        number = q.removeprefix("#")
        if number.isdecimal() and len(number) < 19:
            search |= Q(pk=int(number))
        queryset = queryset.filter(search)
    if status_filter in Order.Status.values:
        queryset = queryset.filter(status=status_filter)
    else:
        status_filter = ""
    return render(request, "shop/staff_orders.html", {
        "page_obj": _page(request, queryset), "q": q, "status_filter": status_filter,
        "status_choices": STATUS_CHOICES, "active_section": "orders",
    })


@require_http_methods(["GET", "HEAD", "POST"])
def order_detail(request, pk):
    _require_view(request, "order")
    order = get_object_or_404(Order.objects.select_related("user", "payment"), pk=pk)
    can_change = request.user.has_perm("shop.change_order")
    error = ""
    if request.method == "POST":
        if not can_change:
            raise PermissionDenied
        action = request.POST.get("action")
        try:
            if action == "cancel":
                cancel_order(order, by_staff=True)
            elif action == "confirm_payment":
                confirm_payment(order)
            elif action in ("ship", "deliver"):
                fulfill_order(order, Order.Status.SHIPPED if action == "ship" else Order.Status.DELIVERED)
            else:
                error = "Неизвестное действие. Выберите действие для заказа."
        except (CancelNotAllowedError, OrderTransitionError):
            error = "Статус заказа уже изменился или это действие недоступно. Обновите страницу."
        if not error:
            messages.success(request, f"Заказ №{order.pk} обновлён.")
            return redirect("staff_order_detail", pk=order.pk)
        order.refresh_from_db()
    payment = getattr(order, "payment", None)
    return render(request, "shop/staff_order_detail.html", {
        "order": order, "items": order.items.select_related("product"),
        "can_ship": can_change and (order.status == Order.Status.PAID or (
            order.status == Order.Status.PENDING and payment is not None and payment.method == "cash_on_delivery")),
        "can_confirm_payment": can_change and order.status == Order.Status.PENDING and payment is not None
                               and payment.method in ("bank_transfer", "qr") and payment.status == "pending",
        "payment": payment,
        "can_deliver": can_change and order.status == Order.Status.SHIPPED,
        "can_cancel": can_change and order.status in STAFF_CAN_CANCEL,
        "error": error, "active_section": "orders",
    })


@require_safe
def users(request):
    _require_view(request, "user")
    q = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "")
    queryset = User.objects.order_by("-date_joined", "-pk")
    if not request.user.is_superuser:
        queryset = queryset.filter(is_staff=False, is_superuser=False, role=User.Role.CUSTOMER)
    if role_filter in User.Role.values:
        queryset = queryset.filter(role=role_filter)
    else:
        role_filter = ""
    if q:
        queryset = queryset.filter(
            Q(username__icontains=q) | Q(email__icontains=q) |
            Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(phone__icontains=q),
        )
    return render(request, "shop/staff_users.html", {
        "page_obj": _page(request, queryset), "q": q, "active_section": "users",
        "role_filter": role_filter, "role_choices": ROLE_CHOICES,
    })
