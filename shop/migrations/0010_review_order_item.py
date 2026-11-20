import django.db.models.deletion
from django.db import migrations, models


def link_existing_reviews(apps, schema_editor):
    """Preserve all reviews; attach only purchases already paid when written."""
    Review = apps.get_model("shop", "Review")
    OrderItem = apps.get_model("shop", "OrderItem")
    database = schema_editor.connection.alias
    for review in Review.objects.using(database).order_by("created_at", "pk").iterator():
        item = (OrderItem.objects.using(database).filter(
            order__user_id=review.user_id, product_id=review.product_id,
            order__status__in=("paid", "shipped", "delivered"),
            order__payment__status="paid", order__payment__paid_at__lte=review.created_at,
            order__created_at__lte=review.created_at, review__isnull=True,
        ).order_by("order__created_at", "pk").first())
        if item:
            Review.objects.using(database).filter(pk=review.pk).update(order_item_id=item.pk)


class Migration(migrations.Migration):
    dependencies = [("shop", "0009_complaint")]

    operations = [
        migrations.AddField(
            model_name="review", name="order_item",
            field=models.OneToOneField(
                blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                related_name="review", to="shop.orderitem",
            ),
        ),
        migrations.RunPython(link_existing_reviews, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name="review", name="review_one_per_user_product"),
    ]
