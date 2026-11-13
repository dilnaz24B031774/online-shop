"""Management access, CRUD validation, and order accounting regressions."""
from decimal import Decimal

from django.contrib.auth.models import Permission
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Category, Notification, Order, OrderItem, Payment, Product, User


class StaffPanelTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("staffadmin", "admin@test.example", "Strong2026!")
        cls.customer = User.objects.create_user("buyer", "buyer@test.example", "Strong2026!")
        cls.viewer = User.objects.create_user(
            "viewer", "viewer@test.example", "Strong2026!", is_staff=True,
        )
        cls.category = Category.objects.create(name_en="Accessories", name_ru="Аксессуары")
        cls.product = Product.objects.create(
            category=cls.category, name_en="Mouse", name_ru="Мышь", sku="MOUSE", price="10.00", stock_quantity=7,
        )
        cls.order = Order.objects.create(
            user=cls.customer, status=Order.Status.PAID, total_amount="20.00", shipping_address="Almaty, Abay 1",
        )
        OrderItem.objects.create(order=cls.order, product=cls.product, quantity=2, unit_price="10.00")
        Payment.objects.create(
            order=cls.order, amount="20.00", method=Payment.Method.CARD,
            status=Payment.Status.PAID, paid_at=timezone.now(),
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def grant(self, *codenames):
        self.viewer.user_permissions.add(*Permission.objects.filter(codename__in=codenames, content_type__app_label="shop"))
        self.client.force_login(self.viewer)

    def product_data(self, **changes):
        data = {
            "name_en": "Keyboard", "name_ru": "Клавиатура", "sku": "KEYBOARD",
            "category": self.category.pk, "price": "35.50", "stock_quantity": "4", "is_active": "on",
        }
        data.update(changes)
        return data

    def test_public_and_customers_are_redirected_from_all_management_pages(self):
        urls = [
            reverse("staff_dashboard"), reverse("staff_catalog"), reverse("staff_product_add"),
            reverse("staff_product_edit", args=[self.product.pk]),
            reverse("staff_product_delete", args=[self.product.pk]),
            reverse("staff_categories"), reverse("staff_category_add"),
            reverse("staff_category_edit", args=[self.category.pk]),
            reverse("staff_category_delete", args=[self.category.pk]),
            reverse("staff_orders"), reverse("staff_order_detail", args=[self.order.pk]), reverse("staff_users"),
        ]
        for user in (None, self.customer):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in urls:
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 302)
                    self.assertIn(reverse("admin:login"), response.url)

    def test_staff_without_model_permissions_cannot_read_or_write(self):
        self.client.force_login(self.viewer)
        for name in ("staff_dashboard", "staff_catalog", "staff_categories", "staff_orders", "staff_users"):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)
        self.assertEqual(self.client.post(reverse("staff_product_add"), self.product_data()).status_code, 403)
        self.assertEqual(self.client.post(reverse("staff_order_detail", args=[self.order.pk]), {"action": "cancel"}).status_code, 403)

    def test_catalog_viewer_can_read_but_cannot_edit_delete_or_see_orders(self):
        self.grant("view_product")
        self.assertEqual(self.client.get(reverse("staff_catalog")).status_code, 200)
        self.assertEqual(self.client.get(reverse("staff_product_edit", args=[self.product.pk])).status_code, 403)
        self.assertEqual(self.client.post(reverse("staff_product_delete", args=[self.product.pk])).status_code, 403)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.context["stats"]["products"], 1)
        self.assertIsNone(response.context["stats"]["revenue"])
        self.assertIsNone(response.context["stats"]["customers"])
        self.assertFalse(response.context["recent_orders"])

    def test_user_role_alone_does_not_grant_management_access(self):
        self.customer.role = User.Role.ADMIN
        self.customer.save(update_fields=["role"])
        self.client.force_login(self.customer)
        self.assertEqual(self.client.get(reverse("staff_dashboard")).status_code, 302)

    def test_employee_user_list_excludes_privileged_accounts(self):
        self.grant("view_user")
        response = self.client.get(reverse("staff_users"))
        self.assertEqual([u.pk for u in response.context["page_obj"]], [self.customer.pk])

    def test_user_search_supports_phone_as_advertised(self):
        User.objects.filter(pk=self.customer.pk).update(phone="+77001234567")
        response = self.client.get(reverse("staff_users"), {"q": "1234567"})
        self.assertEqual([u.pk for u in response.context["page_obj"]], [self.customer.pk])

    def test_order_search_supports_buyer_name_and_displayed_number(self):
        User.objects.filter(pk=self.customer.pk).update(first_name="Айгерим")
        for q in ("Айгерим", f"#{self.order.pk}"):
            with self.subTest(q=q):
                response = self.client.get(reverse("staff_orders"), {"q": q})
                self.assertEqual([o.pk for o in response.context["page_obj"]], [self.order.pk])

    def test_admin_can_render_every_management_section(self):
        for name in ("staff_dashboard", "staff_catalog", "staff_categories", "staff_orders", "staff_users"):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 200)
        self.assertEqual(self.client.get(reverse("staff_order_detail", args=[self.order.pk])).status_code, 200)

    def test_creates_and_updates_product_without_touching_order_history(self):
        response = self.client.post(reverse("staff_product_add"), self.product_data())
        self.assertRedirects(response, reverse("staff_catalog"))
        product = Product.objects.get(sku="KEYBOARD")
        self.assertEqual(product.price, Decimal("35.50"))
        response = self.client.post(
            reverse("staff_product_edit", args=[product.pk]), self.product_data(price="45.00", is_active=""),
        )
        self.assertEqual(response.status_code, 302)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("45.00"))
        self.assertFalse(product.is_active)
        self.assertEqual(self.order.items.get().unit_price, Decimal("10.00"))

    def test_invalid_product_price_and_duplicate_sku_are_form_errors(self):
        for data in (self.product_data(price="0"), self.product_data(price="-1"), self.product_data(sku="MOUSE")):
            response = self.client.post(reverse("staff_product_add"), data)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)
        self.assertEqual(Product.objects.count(), 1)

    def test_delete_confirmation_get_never_deletes(self):
        unsold = Product.objects.create(category=self.category, sku="UNSOLD", name_en="Unsold", price="1.00")
        url = reverse("staff_product_delete", args=[unsold.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertTrue(Product.objects.filter(pk=unsold.pk).exists())
        self.assertRedirects(self.client.post(url), reverse("staff_catalog"))
        self.assertFalse(Product.objects.filter(pk=unsold.pk).exists())

    def test_sold_product_and_used_category_cannot_be_deleted(self):
        for name, obj in (("staff_product_delete", self.product), ("staff_category_delete", self.category)):
            response = self.client.post(reverse(name, args=[obj.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["error"])
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists())
        self.assertEqual(self.order.items.count(), 1)

    def test_category_create_edit_delete_and_unique_validation(self):
        url = reverse("staff_category_add")
        self.assertRedirects(self.client.post(url, {"name_en": "Shoes", "is_active": "on"}), reverse("staff_categories"))
        category = Category.objects.get(name_en="Shoes")
        response = self.client.post(reverse("staff_category_edit", args=[category.pk]), {"name_en": "Footwear", "name_ru": "Обувь"})
        self.assertEqual(response.status_code, 302)
        category.refresh_from_db()
        self.assertEqual(category.name_ru, "Обувь")
        self.assertFalse(category.is_active)
        duplicate = self.client.post(url, {"name_en": "Accessories"})
        self.assertTrue(duplicate.context["form"].errors)
        self.assertEqual(self.client.post(reverse("staff_category_delete", args=[category.pk])).status_code, 302)
        self.assertFalse(Category.objects.filter(pk=category.pk).exists())

    def test_catalog_filter_search_and_pagination(self):
        Product.objects.bulk_create([
            Product(category=self.category, sku=f"SKU{i}", name_en=f"Extra {i:02}", price="1.00", stock_quantity=2)
            for i in range(25)
        ])
        response = self.client.get(reverse("staff_catalog"), {"stock": "low", "category": self.category.pk})
        self.assertEqual(response.context["page_obj"].paginator.count, 25)
        self.assertEqual(len(response.context["page_obj"]), 20)
        response = self.client.get(reverse("staff_catalog"), {"q": "Мышь"})
        self.assertEqual([p.pk for p in response.context["page_obj"]], [self.product.pk])
        response = self.client.get(reverse("staff_catalog"), {"category": "not-a-number", "page": "bad"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["category_filter"], "")

    def test_order_viewer_cannot_trigger_changes(self):
        self.grant("view_order")
        url = reverse("staff_order_detail", args=[self.order.pk])
        self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.post(url, {"action": "ship"}).status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_order_actions_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        response = client.post(reverse("staff_order_detail", args=[self.order.pk]), {"action": "cancel"})
        self.assertEqual(response.status_code, 403)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_get_action_parameters_never_change_order(self):
        response = self.client.get(reverse("staff_order_detail", args=[self.order.pk]), {"action": "cancel"})
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)

    def test_ship_deliver_preserves_stock_payment_and_notifies_customer(self):
        url = reverse("staff_order_detail", args=[self.order.pk])
        for action, status in (("ship", Order.Status.SHIPPED), ("deliver", Order.Status.DELIVERED)):
            self.assertRedirects(self.client.post(url, {"action": action}), url)
            self.order.refresh_from_db()
            self.assertEqual(self.order.status, status)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)
        self.assertEqual(self.order.payment.status, Payment.Status.PAID)
        self.assertEqual(Notification.objects.filter(order=self.order).count(), 2)

    def test_skipped_or_unknown_order_transition_is_rejected(self):
        url = reverse("staff_order_detail", args=[self.order.pk])
        for action in ("deliver", "mark_everything_paid"):
            response = self.client.post(url, {"action": action})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["error"])
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PAID)
        self.assertFalse(Notification.objects.filter(order=self.order).exists())

    def test_cancellation_restores_stock_and_refunds_only_once(self):
        url = reverse("staff_order_detail", args=[self.order.pk])
        self.assertRedirects(self.client.post(url, {"action": "cancel"}), url)
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)
        self.assertEqual(self.order.payment.status, Payment.Status.REFUNDED)
        repeat = self.client.post(url, {"action": "cancel"})
        self.assertEqual(repeat.status_code, 200)
        self.assertTrue(repeat.context["error"])
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 9)
        self.assertEqual(Notification.objects.filter(order=self.order).count(), 1)

    def test_delivered_order_cannot_be_cancelled(self):
        Order.objects.filter(pk=self.order.pk).update(status=Order.Status.DELIVERED)
        response = self.client.post(reverse("staff_order_detail", args=[self.order.pk]), {"action": "cancel"})
        self.assertTrue(response.context["error"])
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 7)
        self.assertEqual(self.order.status, Order.Status.DELIVERED)

    def test_dashboard_excludes_cancelled_sales_and_flags_low_stock(self):
        Order.objects.create(user=self.customer, status=Order.Status.CANCELLED, total_amount="500.00", shipping_address="A")
        Product.objects.filter(pk=self.product.pk).update(stock_quantity=3)
        response = self.client.get(reverse("staff_dashboard"))
        self.assertEqual(response.context["stats"]["revenue"], Decimal("20.00"))
        self.assertEqual(response.context["stats"]["low_stock"], 1)
        self.assertEqual(response.context["stats"]["pending_orders"], 1)
