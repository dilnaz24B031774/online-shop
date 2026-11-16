from django.apps import AppConfig
from django.db.models.signals import post_migrate


def add_complaint_permissions(sender, using, **kwargs):
    """Give the existing managed staff group access to the new complaints inbox."""
    from django.contrib.auth.models import Group, Permission

    from .roles import MANAGER_GROUP

    group = Group.objects.using(using).filter(name=MANAGER_GROUP).first()
    if group is not None:
        permissions = Permission.objects.using(using).filter(
            content_type__app_label="shop", content_type__model="complaint",
            codename__in=("view_complaint", "change_complaint"),
        )
        group.permissions.add(*permissions)


class ShopConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "shop"

    def ready(self):
        post_migrate.connect(
            add_complaint_permissions, sender=self,
            dispatch_uid="shop.complaint_manager_permissions",
        )
