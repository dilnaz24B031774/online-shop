from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase

from .admin import MANAGER_GROUP, OrderItemInline
from .models import Category, Order, OrderItem, Payment, Product, User
from .roles import sync_role_access


class ShopAdminTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.root = User.objects.create_superuser("root", "root@example.com", role=User.Role.ADMIN)
        cls.staff = User.objects.create_user("staff", "staff@example.com", is_staff=True, role=User.Role.MANAGER)
        cls.staff.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="shop", codename__in=["view_user", "change_user", "add_user", "delete_user"],
        ))
        cls.customer = User.objects.create_user("buyer", "buyer@example.com")
        cls.category = Category.objects.create(name_en="Electronics")
        cls.product = Product.objects.create(category=cls.category, sku="TEST-ADMIN", name_en="Mouse",
                                             price=Decimal("25.00"), stock_quantity=4)
        cls.order = Order.objects.create(user=cls.customer, shipping_address="Almaty, Abay 10",
                                        status=Order.Status.PAID, total_amount=Decimal("50.00"))
        cls.item = OrderItem.objects.create(order=cls.order, product=cls.product, quantity=2, unit_price=25)
        cls.payment = Payment.objects.create(order=cls.order, method=Payment.Method.CARD, amount=50,
                                            status=Payment.Status.PENDING)

    def request_for(self, user):
        request = RequestFactory().get("/admin/")
        request.user = user
        return request

    def test_order_history_cannot_be_edited_or_deleted(self):
        model_admin = admin.site._registry[Order]
        request = self.request_for(self.root)
        fields = model_admin.get_form(request, self.order).base_fields
        self.assertNotIn("status", fields)
        self.assertNotIn("total_amount", fields)
        self.assertNotIn("user", fields)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_delete_permission(request, self.order))
        inline = OrderItemInline(Order, admin.site)
        self.assertFalse(inline.has_add_permission(request, self.order))
        self.assertFalse(inline.has_change_permission(request, self.order))
        self.assertFalse(inline.can_delete)

    def test_payment_history_is_read_only(self):
        model_admin = admin.site._registry[Payment]
        request = self.request_for(self.root)
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, self.payment))
        self.assertFalse(model_admin.has_delete_permission(request, self.payment))
        self.assertIn("amount", model_admin.get_readonly_fields(request, self.payment))
        self.assertIn("status", model_admin.get_readonly_fields(request, self.payment))

    def test_staff_cannot_access_or_change_employee_accounts(self):
        model_admin = admin.site._registry[User]
        request = self.request_for(self.staff)
        self.assertFalse(model_admin.has_view_permission(request, self.root))
        self.assertFalse(model_admin.has_change_permission(request, self.root))
        self.assertFalse(model_admin.has_change_permission(request, self.staff))
        self.assertFalse(model_admin.has_delete_permission(request, self.root))
        self.assertQuerySetEqual(model_admin.get_queryset(request), [self.customer], ordered=False)
        self.client.force_login(self.staff)
        response = self.client.post(f"/admin/shop/user/{self.root.pk}/password/", {
            "password1": "OtherStrong2026!", "password2": "OtherStrong2026!",
        })
        self.assertIn(response.status_code, (302, 403, 404))
        self.root.refresh_from_db()
        self.assertFalse(self.root.check_password("OtherStrong2026!"))

    def test_staff_form_and_crafted_post_cannot_grant_privileges(self):
        model_admin = admin.site._registry[User]
        request = self.request_for(self.staff)
        form_class = model_admin.get_form(request, self.customer)
        for field in ("role", "is_staff", "is_superuser", "groups", "user_permissions"):
            self.assertNotIn(field, form_class.base_fields)
        self.client.force_login(self.staff)
        response = self.client.post(f"/admin/shop/user/{self.customer.pk}/change/", {
            "username": "buyer", "email": "buyer@example.com", "first_name": "Updated",
            "last_name": "", "phone": "", "preferred_language": "en", "is_active": "on",
            "role": "admin", "is_staff": "on", "is_superuser": "on",
            "user_permissions": [Permission.objects.get(codename="change_user", content_type__app_label="shop").pk],
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.first_name, "Updated")
        self.assertEqual(self.customer.role, User.Role.CUSTOMER)
        self.assertFalse(self.customer.is_staff)
        self.assertFalse(self.customer.is_superuser)
        self.assertFalse(self.customer.user_permissions.exists())

    def test_superuser_can_create_manager_with_limited_operational_permissions(self):
        self.client.force_login(self.root)
        response = self.client.post("/admin/shop/user/add/", {
            "username": "operator", "email": "operator@example.com", "first_name": "Operator",
            "last_name": "", "phone": "", "preferred_language": "ru", "role": "manager",
            "password1": "CatalogStrong2026!", "password2": "CatalogStrong2026!", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        manager = User.objects.get(username="operator")
        self.assertTrue(manager.is_staff)
        self.assertFalse(manager.is_superuser)
        self.assertTrue(manager.groups.filter(name=MANAGER_GROUP).exists())
        self.assertTrue(manager.has_perm("shop.change_product"))
        self.assertTrue(manager.has_perm("shop.change_order"))
        self.assertFalse(manager.has_perm("shop.change_user"))
        self.assertTrue(manager.check_password("CatalogStrong2026!"))

    def test_superuser_cannot_accidentally_lock_out_own_account(self):
        model_admin = admin.site._registry[User]
        request = self.request_for(self.root)
        form_class = model_admin.get_form(request, self.root)
        form = form_class(data={
            "username": "root", "email": "root@example.com", "first_name": "", "last_name": "",
            "phone": "", "preferred_language": "en", "role": "customer", "is_active": "on",
        }, instance=self.root)
        self.assertFalse(form.is_valid())
        self.assertIn("role", form.errors)

    def test_customer_demotion_removes_all_groups_and_direct_permissions(self):
        extra_group = Group.objects.create(name="Extra catalogue access")
        product_permission = Permission.objects.get(
            codename="change_product", content_type__app_label="shop",
        )
        extra_group.permissions.add(product_permission)
        self.staff.groups.add(extra_group)
        self.staff.user_permissions.add(product_permission)
        # The form submits existing selections when only the role is changed.
        # Demotion must revoke both selected and automatically assigned grants.
        self.client.force_login(self.root)
        response = self.client.post(f"/admin/shop/user/{self.staff.pk}/change/", {
            "username": "staff", "email": "staff@example.com", "first_name": "",
            "last_name": "", "phone": "", "preferred_language": "en", "is_active": "on",
            "role": "customer", "groups": [extra_group.pk],
            "user_permissions": list(self.staff.user_permissions.values_list("pk", flat=True)),
            "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        customer = User.objects.get(pk=self.staff.pk)
        self.assertEqual(customer.role, User.Role.CUSTOMER)
        self.assertFalse(customer.is_staff)
        self.assertFalse(customer.is_superuser)
        self.assertFalse(customer.groups.exists())
        self.assertFalse(customer.user_permissions.exists())
        self.assertFalse(customer.has_perm("shop.change_product"))

    def test_view_only_staff_cannot_change_customer_or_password(self):
        viewer = User.objects.create_user("viewer", "viewer@example.com", is_staff=True, role="manager")
        viewer.user_permissions.add(Permission.objects.get(
            codename="view_user", content_type__app_label="shop",
        ))
        self.client.force_login(viewer)
        response = self.client.get(f"/admin/shop/user/{self.customer.pk}/change/")
        self.assertEqual(response.status_code, 200)
        response = self.client.post(f"/admin/shop/user/{self.customer.pk}/change/", {
            "username": "buyer", "email": "buyer@example.com", "first_name": "Forbidden",
            "preferred_language": "en", "is_active": "on", "_save": "Save",
        })
        self.assertEqual(response.status_code, 403)
        response = self.client.post(f"/admin/shop/user/{self.customer.pk}/password/", {
            "password1": "OtherStrong2026!", "password2": "OtherStrong2026!",
        })
        self.assertEqual(response.status_code, 403)
        self.customer.refresh_from_db()
        self.assertNotEqual(self.customer.first_name, "Forbidden")
        self.assertFalse(self.customer.check_password("OtherStrong2026!"))

    def test_admin_to_manager_transition_revokes_prior_elevated_grants(self):
        old_admin = User.objects.create_superuser("oldadmin", "oldadmin@example.com", role=User.Role.ADMIN)
        elevated = Group.objects.create(name="Old administration access")
        permission = Permission.objects.get(codename="change_user", content_type__app_label="shop")
        elevated.permissions.add(permission)
        old_admin.groups.add(elevated)
        old_admin.user_permissions.add(permission)
        self.client.force_login(self.root)
        response = self.client.post(f"/admin/shop/user/{old_admin.pk}/change/", {
            "username": "oldadmin", "email": "oldadmin@example.com", "first_name": "", "last_name": "",
            "phone": "", "preferred_language": "ru", "role": "manager", "is_active": "on",
            "groups": [elevated.pk], "user_permissions": [permission.pk], "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        manager = User.objects.get(pk=old_admin.pk)
        self.assertTrue(manager.is_staff)
        self.assertFalse(manager.is_superuser)
        self.assertEqual(list(manager.groups.values_list("name", flat=True)), [MANAGER_GROUP])
        self.assertFalse(manager.user_permissions.exists())
        self.assertFalse(manager.has_perm("shop.change_user"))
        self.assertTrue(manager.has_perm("shop.change_order"))

    def test_existing_manager_sync_preserves_explicit_custom_grants(self):
        extra_group = Group.objects.create(name="Extra reporting visibility")
        self.staff.groups.add(extra_group)
        sync_role_access(self.staff, previous_role=User.Role.MANAGER)
        self.assertTrue(self.staff.groups.filter(pk=extra_group.pk).exists())
        self.assertTrue(self.staff.groups.filter(name=MANAGER_GROUP).exists())
        self.assertTrue(self.staff.user_permissions.exists())

    def test_role_filter_does_not_expose_employees_to_other_managers(self):
        self.client.force_login(self.root)
        response = self.client.get("/staff/users/", {"role": "manager"})
        self.assertEqual([user.pk for user in response.context["page_obj"]], [self.staff.pk])
        response = self.client.get("/staff/users/", {"role": "invalid"})
        self.assertEqual(response.context["role_filter"], "")
        self.client.force_login(self.staff)
        response = self.client.get("/staff/users/", {"role": "admin"})
        self.assertFalse(response.context["page_obj"])
        self.assertContains(response, "Панель менеджера")


class ManagerCreationTests(TestCase):
    password = "ShopOperations2026!Qx"

    def create(self, username="operator", password=None, **options):
        output = StringIO()
        with patch("sys.stdin", StringIO((password or self.password) + "\n")):
            call_command("create_manager", username, email=options.pop("email", "operator@example.com"),
                         password_stdin=True, stdout=output, **options)
        return output.getvalue()

    def test_command_creates_limited_manager_and_never_prints_password(self):
        output = self.create()
        manager = User.objects.get(username="operator")
        self.assertTrue(manager.check_password(self.password))
        self.assertNotIn(self.password, output)
        self.assertTrue(manager.is_staff)
        self.assertFalse(manager.is_superuser)
        self.assertEqual(manager.role, User.Role.MANAGER)
        for permission in ("shop.change_product", "shop.change_category", "shop.change_order", "shop.view_user"):
            self.assertTrue(manager.has_perm(permission))
        for permission in ("shop.change_user", "shop.delete_user", "auth.change_group", "auth.add_permission"):
            self.assertFalse(manager.has_perm(permission))

    def test_command_validates_password_before_creating_an_account(self):
        with self.assertRaises(CommandError):
            self.create(password="123")
        self.assertFalse(User.objects.filter(username="operator").exists())

    def test_command_never_overwrites_an_existing_account_implicitly(self):
        original = User.objects.create_user("operator", "original@example.com", "OriginalStrong2026!Qx")
        with self.assertRaises(CommandError):
            self.create()
        original.refresh_from_db()
        self.assertEqual(original.email, "original@example.com")
        self.assertEqual(original.role, User.Role.CUSTOMER)
        self.assertTrue(original.check_password("OriginalStrong2026!Qx"))

    def test_explicit_update_replaces_admin_privileges_with_manager_policy(self):
        original = User.objects.create_superuser("operator", "original@example.com", role=User.Role.ADMIN)
        original.user_permissions.add(Permission.objects.get(codename="change_user", content_type__app_label="shop"))
        self.create(update_existing=True)
        manager = User.objects.get(pk=original.pk)
        self.assertFalse(manager.is_superuser)
        self.assertEqual(manager.email, "operator@example.com")
        self.assertTrue(manager.check_password(self.password))
        self.assertFalse(manager.has_perm("shop.change_user"))

    def test_duplicate_email_does_not_partially_create_manager(self):
        User.objects.create_user("buyer", "operator@example.com")
        with self.assertRaises(CommandError):
            self.create()
        self.assertFalse(User.objects.filter(username="operator").exists())
