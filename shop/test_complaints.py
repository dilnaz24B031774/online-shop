"""Complaints are private, owner-scoped and cannot be answered by customers."""
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from .models import Complaint, Order, User


class CustomerComplaintTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.buyer = User.objects.create_user("complaint_buyer", "buyer@example.test", "Strong2026!")
        cls.other = User.objects.create_user("complaint_other", "other@example.test", "Strong2026!")
        cls.staff = User.objects.create_user("complaint_staff", "staff@example.test", "Strong2026!", is_staff=True)
        cls.order = Order.objects.create(user=cls.buyer, shipping_address="Almaty", total_amount="20.00")
        cls.other_order = Order.objects.create(user=cls.other, shipping_address="Astana", total_amount="35.00")
        cls.mine = Complaint.objects.create(
            user=cls.buyer, order=cls.order, category=Complaint.Category.DELIVERY,
            subject="Delivery delay", message="The parcel has not arrived yet.",
        )
        cls.theirs = Complaint.objects.create(
            user=cls.other, subject="Private complaint", message="This message belongs to another customer.",
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.buyer)

    def create(self, **changes):
        return self.api.post("/api/complaints/", {
            "subject": "  Damaged parcel  ", "message": "  The package arrived damaged.  ",
            "category": "delivery", "order": self.order.pk, **changes,
        }, format="json")

    def test_anonymous_cannot_read_or_create_complaints(self):
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get("/api/complaints/").status_code, 401)
        self.assertEqual(self.api.get(f"/api/complaints/{self.mine.pk}/").status_code, 401)
        self.assertEqual(self.create().status_code, 401)

    def test_list_and_details_only_expose_own_complaints(self):
        result = self.api.get("/api/complaints/")
        self.assertEqual(result.status_code, 200)
        self.assertEqual([row["id"] for row in result.json()], [self.mine.pk])
        self.assertNotIn("Private complaint", result.content.decode())
        self.assertEqual(self.api.get(f"/api/complaints/{self.theirs.pk}/").status_code, 404)
        self.assertEqual(self.api.get("/api/complaints/999999999/").status_code, 404)
        response = self.api.get(f"/api/complaints/{self.mine.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["order"], self.order.pk)
        for key in ("user", "email", "phone", "responded_by"):
            self.assertNotIn(key, response.json())

    def test_create_saves_owner_and_trimmed_content(self):
        response = self.create()
        self.assertEqual(response.status_code, 201)
        complaint = Complaint.objects.get(pk=response.json()["id"])
        self.assertEqual(complaint.user, self.buyer)
        self.assertEqual(complaint.order, self.order)
        self.assertEqual(complaint.subject, "Damaged parcel")
        self.assertEqual(complaint.message, "The package arrived damaged.")
        self.assertEqual(complaint.status, Complaint.Status.NEW)
        self.assertEqual(complaint.staff_response, "")
        self.assertIsNone(complaint.responded_by)
        self.assertIsNone(complaint.replied_at)

    def test_general_complaint_does_not_require_an_order(self):
        response = self.api.post("/api/complaints/", {
            "subject": "Question about service", "message": "Please help me with the store service.",
        }, format="json")
        self.assertEqual(response.status_code, 201)
        complaint = Complaint.objects.get(pk=response.json()["id"])
        self.assertIsNone(complaint.order)
        self.assertEqual(complaint.category, Complaint.Category.OTHER)
        self.assertEqual(self.create(order=None).status_code, 201)

    def test_cannot_attach_another_customers_order(self):
        count = Complaint.objects.count()
        for order in (self.other_order.pk, 999999999):
            with self.subTest(order=order):
                response = self.create(order=order)
                self.assertEqual(response.status_code, 400)
                self.assertIn("order", response.json())
        self.assertEqual(Complaint.objects.count(), count)

    def test_invalid_subject_message_and_category_do_not_create_rows(self):
        count = Complaint.objects.count()
        for payload, key in (
            ({"subject": "   "}, "subject"),
            ({"subject": "a" * 151}, "subject"),
            ({"message": "   "}, "message"),
            ({"message": "short"}, "message"),
            ({"message": "a" * 5001}, "message"),
            ({"category": "unknown"}, "category"),
            ({"order": "invalid"}, "order"),
        ):
            with self.subTest(payload=payload):
                response = self.create(**payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(key, response.json())
        self.assertEqual(Complaint.objects.count(), count)

    def test_customer_cannot_spoof_owner_status_or_staff_response(self):
        response = self.create(
            id=self.theirs.pk, user=self.other.pk, status="resolved",
            staff_response="Forged response", responded_by=self.staff.pk,
            replied_at=timezone.now().isoformat(), created_at="2000-01-01T00:00:00Z",
        )
        self.assertEqual(response.status_code, 201)
        complaint = Complaint.objects.get(pk=response.json()["id"])
        self.assertNotEqual(complaint.pk, self.theirs.pk)
        self.assertEqual(complaint.user, self.buyer)
        self.assertEqual(complaint.status, Complaint.Status.NEW)
        self.assertEqual(complaint.staff_response, "")
        self.assertIsNone(complaint.responded_by)
        self.assertIsNone(complaint.replied_at)
        self.assertGreater(complaint.created_at.year, 2000)

    def test_malformed_order_values_are_rejected_without_server_errors(self):
        count = Complaint.objects.count()
        for value in (1.5, True, False, {}, [], -1, 0, 9223372036854775808, "1e309"):
            with self.subTest(value=value):
                response = self.create(order=value)
                self.assertEqual(response.status_code, 400)
                self.assertIn("order", response.json())
        # This is valid JSON numeric syntax; Python's JSON decoder produces inf.
        for value in ("1e309", "-1e309"):
            with self.subTest(overflow=value):
                response = self.api.post(
                    "/api/complaints/",
                    '{"subject":"Overflow order","message":"Valid complaint body","order":' + value + '}',
                    content_type="application/json",
                )
                self.assertEqual(response.status_code, 400)
                self.assertIn("order", response.json())
        self.assertEqual(Complaint.objects.count(), count)

    def test_customers_cannot_update_or_delete_existing_complaints(self):
        for method in (self.api.patch, self.api.put, self.api.delete):
            with self.subTest(method=method.__name__):
                response = method(f"/api/complaints/{self.mine.pk}/", {"status": "resolved"}, format="json")
                self.assertEqual(response.status_code, 405)
        self.mine.refresh_from_db()
        self.assertEqual(self.mine.status, Complaint.Status.NEW)

    def test_staff_response_and_status_are_visible_to_its_customer(self):
        now = timezone.now()
        Complaint.objects.filter(pk=self.mine.pk).update(
            status=Complaint.Status.RESOLVED, staff_response="We have sent a replacement.",
            responded_by=self.staff, replied_at=now,
        )
        response = self.api.get(f"/api/complaints/{self.mine.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["staff_response"], "We have sent a replacement.")
        self.assertEqual(response.json()["status"], Complaint.Status.RESOLVED)
        self.assertIsNotNone(response.json()["replied_at"])
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get(f"/api/complaints/{self.mine.pk}/").status_code, 404)

    def test_database_enforces_category_and_status_choices(self):
        for column, value in (("status", "public"), ("category", "anything")):
            with self.subTest(column=column), self.assertRaises(IntegrityError), transaction.atomic():
                Complaint.objects.filter(pk=self.mine.pk).update(**{column: value})
