from django import forms
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_safe

from .models import Product


class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = (
            "name_en", "sku", "category", "price", "stock_quantity", "is_active",
            "brand", "image_url", "description_en", "name_ru", "description_ru",
            "name_kk", "description_kk",
        )
        labels = {
            "name_en": "Название (EN)", "category": "Категория", "price": "Цена",
            "stock_quantity": "Остаток", "is_active": "Показывать на витрине",
            "brand": "Бренд", "image_url": "Ссылка на фото", "description_en": "Описание (EN)",
            "name_ru": "Название (RU)", "description_ru": "Описание (RU)",
            "name_kk": "Название (KK)", "description_kk": "Описание (KK)",
        }
        widgets = {field: forms.Textarea(attrs={"rows": 3}) for field in (
            "description_en", "description_ru", "description_kk",
        )}


@require_safe
def catalog(request):
    if not any(request.user.has_perm(perm) for perm in ("shop.view_product", "shop.change_product")):
        raise PermissionDenied
    products = Product.objects.select_related("category").order_by("name_en", "pk")
    return render(request, "shop/staff_catalog.html", {"products": products})


@require_http_methods(["GET", "HEAD", "POST"])
def product_form(request, pk=None):
    permission = "shop.add_product" if pk is None else "shop.change_product"
    if not request.user.has_perm(permission):
        raise PermissionDenied
    product = None if pk is None else get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST if request.method == "POST" else None, instance=product)
    if request.method == "POST" and form.is_valid():
        form.save()
        if pk is None and not any(request.user.has_perm(perm) for perm in ("shop.view_product", "shop.change_product")):
            return redirect("staff_product_add")
        return redirect("staff_catalog")
    return render(request, "shop/staff_catalog.html", {"form": form, "product": product})
