"""
Data for existing databases:
1. Orders created by `seed_shop` become is_demo=True, so "Top", hits and trends count only real purchases.
   Seed orders are recognised by their notification text "Order #12: delivered." (real orders say
   "Order #12 is paid.").
2. Promo codes already used in not-cancelled orders get a PromoRedemption row
   (one per customer and code - the earliest order wins).
"""
import re

from django.db import migrations

SEED_TEXT = re.compile(r"^Order #\d+: (paid|shipped|delivered|cancelled|pending)\.$")


def forwards(apps, schema_editor):
    Order = apps.get_model("shop", "Order")
    Notification = apps.get_model("shop", "Notification")
    PromoRedemption = apps.get_model("shop", "PromoRedemption")

    demo_ids = [n.order_id for n in Notification.objects.exclude(order=None).only("order_id", "message")
                if SEED_TEXT.match(n.message)]
    Order.objects.filter(id__in=demo_ids).update(is_demo=True)

    seen = set()
    for order in (Order.objects.exclude(promo_code=None).exclude(status="cancelled")
                  .order_by("created_at", "id")):
        key = (order.user_id, order.promo_code_id)
        if key in seen:
            continue
        seen.add(key)
        PromoRedemption.objects.create(user_id=order.user_id, promo_id=order.promo_code_id, order_id=order.id)


def backwards(apps, schema_editor):
    apps.get_model("shop", "PromoRedemption").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("shop", "0009_timer_refunds_cards_subscriptions")]
    operations = [migrations.RunPython(forwards, backwards)]
