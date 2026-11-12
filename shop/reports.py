"""Manager reports page: /staff/reports/  (+ CSV download)."""
import csv
from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_safe

from . import services

PERIODS = (("7", "7 дней"), ("30", "30 дней"), ("90", "3 месяца"), ("all", "Всё время"))


def _period(request):
    value = request.GET.get("period", "30")
    if value not in dict(PERIODS):
        value = "30"
    since = None if value == "all" else timezone.now() - timedelta(days=int(value))
    return value, since


def _threshold(request):
    try:
        return max(1, min(1000, int(request.GET.get("threshold", 10))))
    except ValueError:
        return 10


def _check(request):
    # managers and admins: anyone who can see orders and products
    if not (request.user.has_perm("shop.view_order") and request.user.has_perm("shop.view_product")):
        raise PermissionDenied


@require_safe
def reports(request):
    _check(request)
    period, since = _period(request)
    threshold = _threshold(request)
    categories = services.report_sales_by_category(since)
    return render(request, "shop/staff_reports.html", {
        "active_section": "reports", "periods": PERIODS, "period": period, "threshold": threshold,
        "summary": services.report_summary(since),
        "categories": categories,
        "best": services.report_best_sellers(since),
        "low_stock": services.report_low_stock(threshold),
        "promos": services.report_promo_usage(since),
    })


@require_safe
def reports_csv(request, kind):
    _check(request)
    period, since = _period(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="sauda_{kind}_{period}.csv"'
    response.write("﻿")                     # so Excel opens Russian text correctly
    w = csv.writer(response)
    if kind == "categories":
        w.writerow(["Категория", "Продано, шт.", "Выручка, $", "Доля, %"])
        for r in services.report_sales_by_category(since):
            w.writerow([r["name"], r["units"], r["revenue"], r["share"]])
    elif kind == "low-stock":
        w.writerow(["SKU", "Товар", "Категория", "Остаток"])
        for p in services.report_low_stock(_threshold(request)):
            w.writerow([p.sku, p.name_ru or p.name_en, p.category.name_ru or p.category.name_en, p.stock_quantity])
    elif kind == "best-sellers":
        w.writerow(["SKU", "Товар", "Продано, шт.", "Выручка, $", "Остаток"])
        for r in services.report_best_sellers(since, limit=100):
            w.writerow([r["product__sku"], r["product__name_ru"] or r["product__name_en"], r["units"],
                        r["revenue"], r["product__stock_quantity"]])
    else:
        raise PermissionDenied
    return response
