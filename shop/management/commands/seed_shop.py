"""
Fill the database with demo data:   python manage.py seed_shop
Run it again with --reset to delete the shop data and create it again.
"""
from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from shop.models import (
    Address, CartItem, Category, Notification, Order, OrderItem, Payment, Product, Review, User,
)
from .catalog_data import MOCK_PRODUCTS, ORIGINAL_PHOTOS
from .descriptions import DESCRIPTIONS

PASSWORD = "Shop2026!"   # demo password for every demo user

USERS = [
    # username,   email,                  role,       lang, first, last,          phone
    ("admin",     "admin@shop.kz",        "admin",    "en", "Admin",   "Shop",     ""),
    ("manager",   "manager@shop.kz",      "manager",  "ru", "Marat",   "Seitov",   "+77010000001"),
    ("aigerim",   "aigerim@example.com",  "customer", "kk", "Aigerim", "Kairatova", "+77011111111"),
    ("dana",      "dana@example.com",     "customer", "ru", "Dana",    "Sadykova", "+77022222222"),
    ("timur",     "timur@example.com",    "customer", "en", "Timur",   "Akhmetov", ""),
]

CATEGORIES = [
    ("Electronics", "Электроника",       "Электроника"),
    ("Stationery",  "Канцтовары",        "Кеңсе тауарлары"),
    ("Home",        "Товары для дома",   "Үйге арналған тауарлар"),
    ("Books",       "Книги",             "Кітаптар"),
    ("Fashion",     "Одежда",            "Киім"),
    ("Shoes",       "Обувь",             "Аяқ киім"),
    ("Accessories", "Аксессуары",        "Аксессуарлар"),
    ("Beauty",      "Красота",           "Сұлулық"),
    ("Sports",      "Спорт",             "Спорт"),
]

PRODUCTS = [
    # sku,          category,     EN,                 RU,                    KK,                       price,   stock
    ("EL-CABLE-01", "Electronics", "USB-C Cable",     "Кабель USB-C",        "USB-C кабелі",           "12.00", 120),
    ("EL-MOUSE-01", "Electronics", "Wireless Mouse",  "Беспроводная мышь",   "Сымсыз тінтуір",         "25.00",   6),
    ("EL-HEAD-01",  "Electronics", "Headphones",      "Наушники",            "Құлаққап",               "45.00",  15),
    ("ST-NOTE-A5",  "Stationery",  "Notebook A5",     "Тетрадь A5",          "A5 дәптер",               "3.00", 200),
    ("ST-PEN-10",   "Stationery",  "Pen Set (10)",    "Набор ручек (10)",    "Қалам жиынтығы (10)",     "5.00",  80),
    ("HM-BOTTLE",   "Home",        "Water Bottle",    "Бутылка для воды",    "Су бөтелкесі",            "8.00",  45),
    ("HM-LAMP-01",  "Home",        "Desk Lamp",       "Настольная лампа",    "Үстел шамы",             "20.00",   8),
    ("BK-DB-SYS",   "Books",       "Database Systems", "Системы баз данных", "Деректер қоры жүйелері", "30.00",  15),
]

# (customer, days ago, status, method, [(sku, qty), ...])
ORDERS = [
    ("aigerim", 20, "delivered", "card",             [("EL-MOUSE-01", 20), ("HM-LAMP-01", 15)]),
    ("dana",    15, "delivered", "cash_on_delivery", [("EL-CABLE-01", 37), ("HM-BOTTLE", 21)]),
    ("aigerim",  9, "cancelled", "card",             [("EL-MOUSE-01", 5)]),
    ("timur",    5, "shipped",   "bank_transfer",    [("EL-MOUSE-01", 22), ("ST-NOTE-A5", 30)]),
    ("dana",     1, "paid",      "card",             [("BK-DB-SYS", 2), ("ST-PEN-10", 4)]),
    # orders for the mock catalogue with photos
    ("aigerim", 18, "delivered", "card",             [("EL-AIRPD", 30), ("SH-AJ1", 20), ("AC-CLSSG", 15)]),
    ("dana",    12, "delivered", "card",             [("EL-AIRPD", 30), ("FA-SUMDR", 25), ("AC-CLSSG", 20)]),
    ("timur",    7, "shipped",   "bank_transfer",    [("SH-AJ1", 32), ("FA-SUMDR", 20), ("AC-CLSSG", 12), ("BE-LIPST", 10)]),
    ("aigerim",  3, "paid",      "card",             [("EL-IPH13P", 2), ("BE-CKONE", 3), ("SP-FOOTB", 6)]),
]

REVIEWS = [
    ("aigerim", "EL-MOUSE-01", 5, "Very quiet and comfortable."),
    ("dana",    "EL-CABLE-01", 4, "Good cable, fast charging."),
    ("timur",   "EL-MOUSE-01", 4, "Good mouse for the price."),
    ("dana",    "HM-BOTTLE",   5, "Keeps water cold all day."),
    ("aigerim", "EL-AIRPD",    5, "Great sound, the case fits in any pocket."),
    ("dana",    "SH-AJ1",      5, "Comfortable and looks amazing."),
    ("timur",   "EL-IPH13P",   4, "Excellent camera, battery could be better."),
    ("dana",    "FA-SUMDR",    5, "Light fabric, perfect for summer in Almaty."),
    ("aigerim", "BE-CKONE",    4, "Fresh smell that lasts all day."),
    ("timur",   "SP-FOOTB",    5, "Good grip, we play every weekend."),
    ("dana",    "AC-CLSSG",    4, "Stylish and light."),
]


class Command(BaseCommand):
    help = "Create demo data for the Online Shop"

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="delete shop data first")

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts["reset"]:
            for model in (Notification, Review, CartItem, Payment, OrderItem, Order,
                          Product, Category, Address):
                model.objects.all().delete()
            User.objects.filter(username__in=[u[0] for u in USERS]).delete()

        if Product.objects.exists():
            self.stdout.write(self.style.WARNING("Data already exists. Use --reset to recreate."))
            return

        users = {}
        for username, email, role, lang, first, last, phone in USERS:
            u = User(username=username, email=email, role=role, preferred_language=lang,
                     first_name=first, last_name=last, phone=phone,
                     is_staff=role in ("admin", "manager"), is_superuser=role == "admin")
            u.set_password(PASSWORD)          # stores only the hash
            u.save()
            users[username] = u

        addresses = {
            "aigerim": Address.objects.create(user=users["aigerim"], label="Home", city="Almaty",
                                              street="Abay Ave 10", apartment="5", is_default=True),
            "dana": Address.objects.create(user=users["dana"], label="Home", city="Almaty",
                                           street="Satpayev St 5", is_default=True),
            "timur": Address.objects.create(user=users["timur"], label="Work", city="Astana",
                                            street="Mangilik El Ave 55", is_default=True),
        }
        Address.objects.create(user=users["aigerim"], label="Work", city="Almaty",
                               street="Tole Bi St 59", apartment="301")

        cats = {en: Category.objects.create(name_en=en, name_ru=ru, name_kk=kk)
                for en, ru, kk in CATEGORIES}

        products = {}
        for sku, cat, en, ru, kk, price, stock in PRODUCTS:
            products[sku] = Product.objects.create(
                sku=sku, category=cats[cat], name_en=en, name_ru=ru, name_kk=kk,
                description_en=DESCRIPTIONS[sku][0], description_ru=DESCRIPTIONS[sku][1],
                description_kk=DESCRIPTIONS[sku][2],
                price=Decimal(price), stock_quantity=stock, image_url=ORIGINAL_PHOTOS.get(sku, ""),
            )
        for sku, cat, en, ru, kk, price, stock, brand, image, desc in MOCK_PRODUCTS:
            products[sku] = Product.objects.create(
                sku=sku, category=cats[cat], name_en=en, name_ru=ru, name_kk=kk,
                description_en=desc, description_ru=DESCRIPTIONS[sku][1],
                description_kk=DESCRIPTIONS[sku][2],
                price=Decimal(price), stock_quantity=stock, brand=brand, image_url=image,
            )

        now = timezone.now()
        for username, days_ago, status, method, lines in ORDERS:
            order = Order.objects.create(user=users[username], status=status,
                                         shipping_address=addresses[username].full_text())
            total = Decimal("0")
            for sku, qty in lines:
                p = products[sku]
                OrderItem.objects.create(order=order, product=p, quantity=qty, unit_price=p.price)
                total += p.price * qty
            order.total_amount = total
            order.save(update_fields=["total_amount"])
            created = now - timedelta(days=days_ago)
            Order.objects.filter(pk=order.pk).update(created_at=created)
            pay_status = "refunded" if status == "cancelled" else "paid"
            Payment.objects.create(order=order, method=method, amount=total, status=pay_status,
                                   paid_at=created + timedelta(minutes=2),
                                   provider_reference=f"DEMO-{order.pk:06d}")
            Notification.objects.create(user=users[username], order=order,
                                        message=f"Order #{order.pk}: {status}.")

        for username, sku, rating, comment in REVIEWS:
            Review.objects.create(user=users[username], product=products[sku],
                                  rating=rating, comment=comment)

        CartItem.objects.create(user=users["timur"], product=products["EL-HEAD-01"], quantity=1)
        CartItem.objects.create(user=users["timur"], product=products["ST-PEN-10"], quantity=2)

        self.stdout.write(self.style.SUCCESS(
            f"Demo data created: {User.objects.count()} users, {Product.objects.count()} products, "
            f"{Order.objects.count()} orders. Password for all demo users: {PASSWORD}"
        ))
