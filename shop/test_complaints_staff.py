"""Complaint inbox access, response ownership, validation and CSRF regressions."""
from django.contrib import admin
from django.contrib.auth.models import Group, Permission
from django.test import Client, RequestFactory, TestCase
from django.urls import reverse

from .models import Complaint, Order, User
from .roles import MANAGER_GROUP, sync_role_access


class StaffComplaintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = User.objects.create_superuser("complaint_admin", "complaint_admin@example.test", "Strong2026!")
        cls.customer = User.objects.create_user("complaint_buyer", "complaint_buyer@example.test", "Strong2026!")
        cls.other = User.objects.create_user("other_buyer", "other_buyer@example.test", "Strong2026!")
        cls.employee = User.objects.create_user("complaint_employee", "employee@example.test", "Strong2026!", is_staff=True)
        cls.order = Order.objects.create(user=cls.customer, shipping_address="Almaty, Abay 1")
        cls.complaint = Complaint.objects.create(
            user=cls.customer, order=cls.order, category="delivery", subject="Delivery issue",
            message="Please check the delivery date for my order.",
        )

    def setUp(self):
        self.client.force_login(self.admin)
        self.inbox = reverse("staff_complaints")
        self.detail = reverse("staff_complaint_detail", args=[self.complaint.pk])

    def grant(self, *codenames):
        self.employee.user_permissions.add(*Permission.objects.filter(
            content_type__app_label="shop", codename__in=codenames,
        ))
        self.client.force_login(self.employee)

    def test_public_and_customers_cannot_access_staff_complaints(self):
        for user in (None, self.customer):
            self.client.logout()
            if user:
                self.client.force_login(user)
            for url in (self.inbox, self.detail):
                with self.subTest(user=user, url=url):
                    response = self.client.get(url)
                    self.assertEqual(response.status_code, 302)
                    self.assertIn(reverse("admin:login"), response.url)
            self.assertEqual(self.client.post(self.detail, {"status": "resolved", "staff_response": "Injected"}).status_code, 302)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, "new")

    def test_staff_without_complaint_permissions_is_denied(self):
        self.client.force_login(self.employee)
        self.assertEqual(self.client.get(self.inbox).status_code, 403)
        self.assertEqual(self.client.get(self.detail).status_code, 403)
        self.assertEqual(self.client.post(self.detail, {"status": "in_progress"}).status_code, 403)

    def test_viewer_reads_but_cannot_respond_or_open_order_link(self):
        self.grant("view_complaint")
        response = self.client.get(self.detail)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Delivery issue")
        self.assertNotContains(response, 'name="staff_response"')
        self.assertNotContains(response, reverse("staff_order_detail", args=[self.order.pk]))
        self.assertEqual(self.client.get(self.inbox).status_code, 200)
        self.assertEqual(self.client.post(self.detail, {"status": "resolved", "staff_response": "Forged response"}).status_code, 403)

    def test_response_sets_actor_time_and_status_without_changing_customer_content(self):
        self.grant("change_complaint")
        response = self.client.post(self.detail, {
            "status": "resolved", "staff_response": "  We have checked the delivery.  ",
            "user": self.other.pk, "message": "Forged buyer text", "subject": "Forged subject",
        })
        self.assertRedirects(response, self.detail)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.status, "resolved")
        self.assertEqual(self.complaint.staff_response, "We have checked the delivery.")
        self.assertEqual(self.complaint.responded_by, self.employee)
        self.assertIsNotNone(self.complaint.replied_at)
        self.assertEqual(self.complaint.user, self.customer)
        self.assertEqual(self.complaint.subject, "Delivery issue")
        self.assertEqual(self.complaint.message, "Please check the delivery date for my order.")
        self.assertEqual(self.complaint.order, self.order)

    def test_resolve_without_response_and_invalid_fields_leave_complaint_unchanged(self):
        for data, field in (
            ({"status": "resolved", "staff_response": "   "}, "staff_response"),
            ({"status": "unknown", "staff_response": "Response"}, "status"),
            ({"status": "in_progress", "staff_response": "A" * 5001}, "staff_response"),
        ):
            with self.subTest(field=field):
                response = self.client.post(self.detail, data)
                self.assertEqual(response.status_code, 200)
                self.assertIn(field, response.context["form"].errors)
                self.complaint.refresh_from_db()
                self.assertEqual(self.complaint.status, "new")
                self.assertEqual(self.complaint.staff_response, "")
                self.assertIsNone(self.complaint.responded_by)

    def test_status_only_change_preserves_response_author_and_timestamp(self):
        self.client.post(self.detail, {"status": "in_progress", "staff_response": "We are investigating."})
        self.complaint.refresh_from_db()
        replied_at = self.complaint.replied_at
        response = self.client.post(self.detail, {"status": "resolved", "staff_response": "We are investigating."})
        self.assertEqual(response.status_code, 302)
        self.complaint.refresh_from_db()
        self.assertEqual(self.complaint.replied_at, replied_at)
        self.assertEqual(self.complaint.responded_by, self.admin)

    def test_search_status_filters_and_pagination(self):
        other = Complaint.objects.create(user=self.other, subject="Payment issue", message="Please check payment.", status="in_progress")
        response = self.client.get(self.inbox, {"q": "complaint_buyer", "status": "new"})
        self.assertEqual(list(response.context["page_obj"]), [self.complaint])
        response = self.client.get(self.inbox, {"status": "in_progress"})
        self.assertEqual(list(response.context["page_obj"]), [other])
        Complaint.objects.bulk_create([
            Complaint(user=self.customer, subject=f"Issue {index}", message="Please check this issue.")
            for index in range(22)
        ])
        response = self.client.get(self.inbox)
        self.assertEqual(len(response.context["page_obj"]), 20)
        self.assertTrue(response.context["page_obj"].has_next())
        self.assertEqual(self.client.get(self.inbox, {"page": "invalid"}).status_code, 200)

    def test_customer_text_and_staff_response_are_escaped(self):
        self.complaint.subject = '<script>alert("subject")</script>'
        self.complaint.message = '<img src=x onerror="alert(1)">\nSecond line'
        self.complaint.staff_response = '<script>alert("response")</script>'
        self.complaint.save()
        self.grant("view_complaint")
        response = self.client.get(self.detail)
        self.assertContains(response, "&lt;script&gt;")
        self.assertContains(response, "&lt;img")
        self.assertContains(response, "<br>Second line", html=False)
        self.assertNotContains(response, '<img src=x')
        self.assertNotContains(response, '<script>alert(')

    def test_staff_posts_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        page = client.get(self.detail)
        self.assertEqual(page.status_code, 200)
        self.assertEqual(client.post(self.detail, {"status": "in_progress", "staff_response": "Checking."}).status_code, 403)
        response = client.post(self.detail, {
            "status": "in_progress", "staff_response": "Checking.",
            "csrfmiddlewaretoken": client.cookies["csrftoken"].value,
        })
        self.assertEqual(response.status_code, 302)

    def test_admin_is_read_only_and_links_to_staff_response_workflow(self):
        model_admin = admin.site._registry[Complaint]
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        self.assertFalse(model_admin.has_add_permission(request))
        self.assertFalse(model_admin.has_change_permission(request, self.complaint))
        self.assertFalse(model_admin.has_delete_permission(request, self.complaint))
        self.assertIn(self.detail, str(model_admin.process_complaint(self.complaint)))
        self.assertEqual(self.client.post(reverse("admin:shop_complaint_change", args=[self.complaint.pk]), {
            "status": "resolved", "staff_response": "",
        }).status_code, 403)

    def test_manager_role_sync_grants_only_complaint_read_and_response_permissions(self):
        self.employee.role = User.Role.MANAGER
        self.employee.save(update_fields=["role"])
        sync_role_access(self.employee)
        self.assertTrue(self.employee.has_perm("shop.view_complaint"))
        self.assertTrue(self.employee.has_perm("shop.change_complaint"))
        self.assertFalse(self.employee.has_perm("shop.add_complaint"))
        self.assertFalse(self.employee.has_perm("shop.delete_complaint"))

    def test_existing_manager_group_receives_new_permissions_without_losing_custom_grants(self):
        from .apps import add_complaint_permissions

        group, _ = Group.objects.get_or_create(name=MANAGER_GROUP)
        custom = Permission.objects.get(content_type__app_label="shop", codename="view_category")
        group.permissions.set([custom])
        unrelated = Group.objects.create(name="Unrelated complaint group")
        add_complaint_permissions(None, using="default")
        add_complaint_permissions(None, using="default")
        self.assertSetEqual(set(group.permissions.values_list("codename", flat=True)), {
            "view_category", "view_complaint", "change_complaint",
        })
        self.assertFalse(unrelated.permissions.exists())
