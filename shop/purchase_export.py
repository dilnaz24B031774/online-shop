"""Full purchase export for administrators: /staff/reports/purchases.csv and .pdf.

Every order in the chosen date range, with the customer, payment, promo code,
items and refunds. Filters come from the query string:
  date_from, date_to  YYYY-MM-DD (default: the last 30 days)
  status              one of Order.Status, or empty for all
  demo=1              include demo orders created by seed_shop
"""
import csv
import io
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_safe

from .models import Order, Payment
from .services import PAID_STATUSES

MAX_PDF_ORDERS = 3000          # a bigger PDF is unreadable; the CSV has no limit

STATUS_LABELS = {
    "pending": "Ждёт оплаты", "paid": "Оплачен", "shipped": "Отправлен", "delivered": "Доставлен",
    "cancelled": "Отменён",
}
METHOD_LABELS = {
    "card": "Карта", "bank_transfer": "Банковский перевод", "cash_on_delivery": "Наличные курьеру",
    "qr": "QR в приложении банка", "installment": "Рассрочка 0-0-12",
}
PAYMENT_STATUS_LABELS = {"pending": "Ожидает", "paid": "Оплачено", "failed": "Ошибка", "refunded": "Возвращено"}


def can_export(user):
    """Customer names, e-mails and addresses: admins, or staff allowed to see both orders and users."""
    return user.is_active and user.is_staff and (
        user.is_superuser or (user.has_perm("shop.view_order") and user.has_perm("shop.view_user")))


def _check(request):
    if not can_export(request.user):
        raise PermissionDenied


def _parse_day(value):
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def export_filters(request):
    """Validated filters with defaults; also used to pre-fill the form on the reports page."""
    today = timezone.localdate()
    date_to = _parse_day(request.GET.get("date_to")) or today
    date_from = _parse_day(request.GET.get("date_from")) or date_to - timedelta(days=29)
    if date_from > date_to:
        date_from, date_to = date_to, date_from
    status = request.GET.get("status", "")
    if status not in Order.Status.values:
        status = ""
    return {"date_from": date_from, "date_to": date_to, "status": status, "demo": request.GET.get("demo") == "1"}


def purchase_orders(filters):
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(filters["date_from"], time.min), tz)
    end = timezone.make_aware(datetime.combine(filters["date_to"] + timedelta(days=1), time.min), tz)
    orders = (Order.objects.filter(created_at__gte=start, created_at__lt=end)
              .select_related("user", "payment", "promo_code")
              .prefetch_related("items__product__category")
              .order_by("created_at", "pk"))
    if filters["status"]:
        orders = orders.filter(status=filters["status"])
    if not filters["demo"]:
        orders = orders.filter(is_demo=False)
    return orders


def _payment(order):
    try:
        return order.payment
    except Payment.DoesNotExist:
        return None


def _customer_name(user):
    full = f"{user.first_name} {user.last_name}".strip()
    return full or user.username


def _product_name(product):
    return product.name_ru or product.name_en


def _safe(value):
    """Stop spreadsheet apps from running text that starts like a formula."""
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def _filename(filters, extension):
    suffix = f"_{filters['status']}" if filters["status"] else ""
    return f"sauda_purchases_{filters['date_from']:%Y%m%d}-{filters['date_to']:%Y%m%d}{suffix}.{extension}"


def summarize(orders):
    paid = [o for o in orders if o.status in PAID_STATUSES]
    refunded = sum(((_payment(o).refunded_amount if _payment(o) else Decimal("0")) for o in paid), Decimal("0"))
    gross = sum((o.total_amount for o in paid), Decimal("0"))
    return {
        "orders": len(orders), "paid_orders": len(paid),
        "revenue": gross - refunded, "refunded": refunded,
        "discounts": sum((o.discount_amount for o in paid), Decimal("0")),
        "units": sum(i.quantity - i.refunded_quantity for o in paid for i in o.items.all()),
        "customers": len({o.user_id for o in orders}),
        "cancelled": sum(1 for o in orders if o.status == Order.Status.CANCELLED),
    }


@require_safe
def purchases_csv(request):
    _check(request)
    filters = export_filters(request)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="{_filename(filters, "csv")}"'
    response["Cache-Control"] = "private, no-store"
    response.write("\ufeff")                     # so Excel opens Russian text correctly
    w = csv.writer(response, delimiter=";")     # Excel with Russian locale expects ";"
    w.writerow(["Заказ №", "Дата", "Статус заказа", "Логин", "Покупатель", "Email", "Телефон", "Город",
                "Адрес доставки", "Способ оплаты", "Статус оплаты", "Оплачено", "Промокод",
                "SKU", "Товар", "Категория", "Кол-во", "Цена, $", "Сумма строки, $", "Возвращено, шт.",
                "Скидка заказа, $", "Итого заказа, $", "Возвращено по заказу, $", "Демо"])
    for order in purchase_orders(filters).iterator(chunk_size=500):
        user, payment = order.user, _payment(order)
        head = [order.pk, timezone.localtime(order.created_at).strftime("%d.%m.%Y %H:%M"),
                STATUS_LABELS.get(order.status, order.status), _safe(user.username), _safe(_customer_name(user)),
                _safe(user.email), _safe(user.phone), _safe(user.city), _safe(order.shipping_address),
                METHOD_LABELS.get(payment.method, payment.method) if payment else "",
                PAYMENT_STATUS_LABELS.get(payment.status, payment.status) if payment else "",
                timezone.localtime(payment.paid_at).strftime("%d.%m.%Y %H:%M") if payment and payment.paid_at else "",
                _safe(order.promo_code.code) if order.promo_code else ""]
        tail = [order.discount_amount, order.total_amount, payment.refunded_amount if payment else Decimal("0"),
                "да" if order.is_demo else ""]
        items = list(order.items.all())
        if not items:
            w.writerow(head + ["", "", "", "", "", "", ""] + tail)
        for item in items:
            product = item.product
            w.writerow(head + [_safe(product.sku), _safe(_product_name(product)),
                               _safe(product.category.name_ru or product.category.name_en),
                               item.quantity, item.unit_price, item.unit_price * item.quantity,
                               item.refunded_quantity] + tail)
    return response


# ---------- PDF ----------

_FONT_CANDIDATES = (
    # (regular, bold): macOS, Windows, Linux. Cyrillic needs a real TrueType font.
    ("/System/Library/Fonts/Supplemental/Arial.ttf", "/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", "/Library/Fonts/Arial Unicode.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/dejavu/DejaVuSans.ttf", "/usr/share/fonts/dejavu/DejaVuSans-Bold.ttf"),
    ("/usr/share/fonts/TTF/DejaVuSans.ttf", "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
)
_fonts = None


def _register_fonts():
    """Return (regular, bold) font names; falls back to Helvetica (no Cyrillic) if nothing is found."""
    global _fonts
    if _fonts:
        return _fonts
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    project_fonts = Path(__file__).resolve().parent / "fonts"
    candidates = ((str(project_fonts / "report.ttf"), str(project_fonts / "report-bold.ttf")),) + _FONT_CANDIDATES
    for regular, bold in candidates:
        if Path(regular).is_file():
            pdfmetrics.registerFont(TTFont("Report", regular))
            pdfmetrics.registerFont(TTFont("Report-Bold", bold if Path(bold).is_file() else regular))
            _fonts = ("Report", "Report-Bold")
            return _fonts
    _fonts = ("Helvetica", "Helvetica-Bold")
    return _fonts


def _money(value):
    return f"${value:,.2f}".replace(",", " ")


def build_pdf(orders, filters, summary, author):
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_RIGHT
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    from xml.sax.saxutils import escape

    regular, bold = _register_fonts()
    green, soft, line, muted = (colors.HexColor("#155a45"), colors.HexColor("#eef5f1"),
                                colors.HexColor("#d7e3dc"), colors.HexColor("#5f7068"))
    base = ParagraphStyle("base", fontName=regular, fontSize=8, leading=10.5)
    small = ParagraphStyle("small", parent=base, fontSize=7, leading=9, textColor=muted)
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    head = ParagraphStyle("head", parent=base, fontName=bold, textColor=colors.white)
    title = ParagraphStyle("title", parent=base, fontName=bold, fontSize=18, leading=22, textColor=green)
    sub = ParagraphStyle("sub", parent=base, fontSize=9, leading=12, textColor=muted)
    stat_value = ParagraphStyle("stat_value", parent=base, fontName=bold, fontSize=13, leading=16, textColor=green)

    buffer = io.BytesIO()
    page = landscape(A4)
    generated = timezone.localtime().strftime("%d.%m.%Y %H:%M")

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont(regular, 7)
        canvas.setFillColor(muted)
        canvas.drawString(14 * mm, 9 * mm, f"Sauda · отчёт о покупках · сформирован {generated} · {author}")
        canvas.drawRightString(page[0] - 14 * mm, 9 * mm, f"Страница {doc.page}")
        canvas.restoreState()

    doc = SimpleDocTemplate(buffer, pagesize=page, leftMargin=14 * mm, rightMargin=14 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title="Sauda — отчёт о покупках", author="Sauda")
    period = f"{filters['date_from']:%d.%m.%Y} — {filters['date_to']:%d.%m.%Y}"
    scope = [STATUS_LABELS[filters["status"]] if filters["status"] else "все статусы",
             "с демо-заказами" if filters["demo"] else "без демо-заказов"]
    story = [Paragraph("Отчёт о покупках", title),
             Paragraph(f"Период: {period} · {', '.join(scope)}", sub), Spacer(1, 6 * mm)]

    stats = [("Заказов", str(summary["orders"])), ("Оплачено", str(summary["paid_orders"])),
             ("Выручка", _money(summary["revenue"])), ("Скидки", _money(summary["discounts"])),
             ("Возвраты", _money(summary["refunded"])), ("Продано, шт.", str(summary["units"])),
             ("Покупателей", str(summary["customers"]))]
    stat_table = Table([[Paragraph(label, small) for label, _ in stats],
                        [Paragraph(value, stat_value) for _, value in stats]],
                       colWidths=[(page[0] - 28 * mm) / len(stats)] * len(stats))
    stat_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), soft), ("BOX", (0, 0), (-1, -1), 0.6, line),
        ("LINEAFTER", (0, 0), (-2, -1), 0.6, line), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5), ("LEFTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [stat_table, Spacer(1, 6 * mm)]

    rows = [[Paragraph(h, head) for h in ("№", "Дата", "Покупатель", "Товары", "Оплата", "Статус",
                                          "Скидка", "Итого")]]
    shown = orders[:MAX_PDF_ORDERS]
    for order in shown:
        user, payment = order.user, _payment(order)
        items = "<br/>".join(
            f"{escape(_product_name(i.product))} × {i.quantity}"
            + (f' <font color="#a8322a">(возврат {i.refunded_quantity})</font>' if i.refunded_quantity else "")
            for i in order.items.all()) or "—"
        customer = (f"{escape(_customer_name(user))}<br/><font size=7 color='#5f7068'>"
                    f"{escape(user.email or user.username)}</font>")
        pay = "—"
        if payment:
            pay = (f"{METHOD_LABELS.get(payment.method, payment.method)}<br/><font size=7 color='#5f7068'>"
                   f"{PAYMENT_STATUS_LABELS.get(payment.status, payment.status)}</font>")
        total = _money(order.total_amount)
        if payment and payment.refunded_amount:
            total += f"<br/><font size=7 color='#a8322a'>−{_money(payment.refunded_amount)}</font>"
        rows.append([Paragraph(str(order.pk), base),
                     Paragraph(timezone.localtime(order.created_at).strftime("%d.%m.%Y<br/>%H:%M"), base),
                     Paragraph(customer, base), Paragraph(items, base), Paragraph(pay, base),
                     Paragraph(STATUS_LABELS.get(order.status, order.status), base),
                     Paragraph(_money(order.discount_amount) if order.discount_amount else "—", right),
                     Paragraph(total, right)])
    if len(rows) == 1:
        rows.append([Paragraph("За выбранный период заказов нет.", base)] + [""] * 7)
    widths = [14 * mm, 22 * mm, 52 * mm, 88 * mm, 36 * mm, 25 * mm, 20 * mm, 24 * mm]
    table = Table(rows, colWidths=widths, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), green), ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, line), ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]
    style += [("BACKGROUND", (0, r), (-1, r), colors.HexColor("#f8faf9")) for r in range(2, len(rows), 2)]
    if len(shown) == 0:
        style.append(("SPAN", (0, 1), (-1, 1)))
    table.setStyle(TableStyle(style))
    story.append(table)
    if len(orders) > MAX_PDF_ORDERS:
        story += [Spacer(1, 4 * mm), Paragraph(
            f"Показаны первые {MAX_PDF_ORDERS} из {len(orders)} заказов. Полный список — в CSV-выгрузке.", sub)]
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return buffer.getvalue()


@require_safe
def purchases_pdf(request):
    _check(request)
    filters = export_filters(request)
    orders = list(purchase_orders(filters))
    pdf = build_pdf(orders, filters, summarize(orders), request.user.get_username())
    response = HttpResponse(pdf, content_type="application/pdf")
    response["Content-Disposition"] = f'attachment; filename="{_filename(filters, "pdf")}"'
    response["Cache-Control"] = "private, no-store"
    return response
