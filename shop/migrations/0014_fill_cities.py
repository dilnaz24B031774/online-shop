from django.db import migrations

# name EN, RU, KK, delivery days min, max
CITIES = [
    ("Almaty", "Алматы", "Алматы", 1, 2),
    ("Astana", "Астана", "Астана", 2, 3),
    ("Shymkent", "Шымкент", "Шымкент", 2, 4),
    ("Karaganda", "Караганда", "Қарағанды", 2, 4),
    ("Aktobe", "Актобе", "Ақтөбе", 3, 5),
    ("Taraz", "Тараз", "Тараз", 2, 4),
    ("Pavlodar", "Павлодар", "Павлодар", 3, 5),
    ("Oskemen", "Усть-Каменогорск", "Өскемен", 3, 5),
    ("Semey", "Семей", "Семей", 3, 5),
    ("Atyrau", "Атырау", "Атырау", 3, 6),
    ("Kostanay", "Костанай", "Қостанай", 3, 5),
    ("Kyzylorda", "Кызылорда", "Қызылорда", 3, 5),
    ("Oral", "Уральск", "Орал", 4, 6),
    ("Petropavl", "Петропавловск", "Петропавл", 3, 5),
    ("Aktau", "Актау", "Ақтау", 4, 6),
    ("Turkistan", "Туркестан", "Түркістан", 2, 4),
    ("Taldykorgan", "Талдыкорган", "Талдықорған", 1, 3),
    ("Kokshetau", "Кокшетау", "Көкшетау", 3, 5),
]


def fill(apps, schema_editor):
    City = apps.get_model("shop", "City")
    for n, (en, ru, kk, dmin, dmax) in enumerate(CITIES):
        City.objects.get_or_create(name_en=en, defaults=dict(
            name_ru=ru, name_kk=kk, delivery_days_min=dmin, delivery_days_max=dmax, sort_order=n))


class Migration(migrations.Migration):
    dependencies = [("shop", "0013_cities_user_city")]
    operations = [migrations.RunPython(fill, migrations.RunPython.noop)]
