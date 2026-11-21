"""Shared role policy for the administration form and local account setup."""
from django.contrib.auth.models import Group, Permission
from django.db import transaction

from .models import User


ROLE_CHOICES = (
    (User.Role.CUSTOMER, "Покупатель"),
    (User.Role.MANAGER, "Менеджер магазина"),
    (User.Role.ADMIN, "Администратор"),
)
MANAGER_GROUP = "Sauda · Менеджеры магазина"
MANAGER_PERMISSIONS = {
    *(f"{action}_{model}" for model in ("product", "category", "review", "notification", "promocode")
      for action in ("add", "change", "delete", "view")),
    "view_order", "change_order", "view_user", "view_payment", "view_address", "view_cartitem",
    "view_complaint", "change_complaint",
}


@transaction.atomic
def sync_role_access(user, *, previous_role=None):
    """Synchronize a saved account's role, staff flags, and operational group.

    Supply the role from before the save. A transition to manager drops older
    grants; ordinary edits of an existing manager retain explicit custom grants.
    Customer accounts always lose employee permissions.
    """
    if user.pk is None:
        raise ValueError("Save the account before synchronizing its role.")
    user.is_staff = user.role in (User.Role.MANAGER, User.Role.ADMIN)
    user.is_superuser = user.role == User.Role.ADMIN
    user.save(update_fields=["is_staff", "is_superuser"])
    if user.role == User.Role.MANAGER:
        group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)
        group.permissions.set(Permission.objects.filter(
            content_type__app_label="shop", codename__in=MANAGER_PERMISSIONS,
        ))
        if previous_role != User.Role.MANAGER:
            user.groups.set([group])
            user.user_permissions.clear()
        else:
            user.groups.add(group)
    elif user.role == User.Role.CUSTOMER:
        user.groups.clear()
        user.user_permissions.clear()
    else:
        user.groups.remove(*Group.objects.filter(name=MANAGER_GROUP))
    # has_perm() caches are attached to the instance, not to its M2M relations.
    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        user.__dict__.pop(cache_name, None)
