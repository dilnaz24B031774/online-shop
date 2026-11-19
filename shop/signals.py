"""When a product comes back in stock (admin, staff panel, any .save()), waiting customers get a notification."""
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from .models import Product


@receiver(pre_save, sender=Product)
def remember_old_stock(sender, instance, **kwargs):
    instance._old_stock = (Product.objects.filter(pk=instance.pk).values_list("stock_quantity", flat=True).first()
                           if instance.pk else None)


@receiver(post_save, sender=Product)
def tell_subscribers(sender, instance, **kwargs):
    if (instance._old_stock or 0) == 0 and instance.stock_quantity > 0:
        from .services import notify_back_in_stock
        transaction.on_commit(lambda: notify_back_in_stock([instance.pk]))
