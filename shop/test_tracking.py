"""Order privacy, validated delivery assignments, and revocable phone GPS sharing."""
from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlsplit

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from .models import DeliveryTracking, Order, User
from .tracking import DeliveryTrackingForm, issue_sharing_token


class TrackingFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.owner = User.objects.create_user("deliverybuyer", "deliverybuyer@example.test", "Strong2026!")
        cls.other = User.objects.create_user("anotherbuyer", "anotherbuyer@example.test", "Strong2026!")
        cls.admin = User.objects.create_superuser("deliveryadmin", "deliveryadmin@example.test", "Strong2026!")
        cls.viewer = User.objects.create_user("deliveryviewer", "deliveryviewer@example.test", "Strong2026!", is_staff=True)
        cls.order = Order.objects.create(user=cls.owner, status=Order.Status.SHIPPED,
                                         shipping_address="Almaty, Abay 10, apartment 2")
        cls.tracking = DeliveryTracking.objects.create(
            order=cls.order, courier_name="Айдос", courier_phone="+77001234567",
            courier_lat="43.240000", courier_lng="76.890000",
            destination_lat="43.250000", destination_lng="76.910000", eta_minutes=12,
            position_updated_at=timezone.now(),
        )

    def setUp(self):
        self.api = APIClient()
        self.api.force_authenticate(self.owner)
        self.url = reverse("order_tracking", args=[self.order.pk])
        self.staff_url = reverse("staff_order_detail", args=[self.order.pk])
        self.session_url = reverse("courier_session")
        self.location_url = reverse("courier_location")

    def share(self):
        raw, _ = issue_sharing_token(self.order)
        return raw

    def location(self, token, **changes):
        return self.api.post(self.location_url, {
            "token": token, "latitude": 43.2456789, "longitude": 76.8956789, "accuracy": 8.5, **changes,
        }, format="json")


class CustomerTrackingTests(TrackingFixture):
    def test_requires_authentication_and_hides_other_customers_orders(self):
        self.api.force_authenticate(None)
        self.assertEqual(self.api.get(self.url).status_code, 401)
        self.api.force_authenticate(self.other)
        self.assertEqual(self.api.get(self.url).status_code, 404)
        self.assertEqual(self.api.get(reverse("order_tracking", args=[999999])).status_code, 404)

    def test_staff_need_relevant_order_permission(self):
        self.api.force_authenticate(self.viewer)
        self.assertEqual(self.api.get(self.url).status_code, 404)
        permission = Permission.objects.get(codename="view_order", content_type__app_label="shop")
        self.viewer.user_permissions.add(permission)
        self.api.force_authenticate(User.objects.get(pk=self.viewer.pk))
        self.assertEqual(self.api.get(self.url).status_code, 200)

    def test_owner_gets_persisted_coordinates_without_internal_tokens(self):
        token = self.share()
        response = self.api.get(self.url)
        data = response.json()
        self.assertEqual(data["status"], "active")
        self.assertEqual(data["source"], "manual")
        self.assertEqual(data["position"], {"lat": 43.24, "lng": 76.89})
        self.assertEqual(data["destination"], {"lat": 43.25, "lng": 76.91})
        self.assertEqual(data["shipping_address"], self.order.shipping_address)
        self.assertEqual(data["courier"], {"name": "Айдос", "phone": "+77001234567"})
        self.assertEqual(data["eta_minutes"], 12)
        self.assertNotIn(token, response.content.decode())
        self.assertNotIn("share_token_hash", data)
        self.assertNotIn("share_expires_at", data)
        self.assertEqual(response["Cache-Control"], "private, no-store")

    def test_missing_assignment_returns_safe_state_without_creating_a_record(self):
        order = Order.objects.create(user=self.owner, status=Order.Status.SHIPPED, shipping_address="Astana")
        count = DeliveryTracking.objects.count()
        response = self.api.get(reverse("order_tracking", args=[order.pk]))
        self.assertEqual(response.json()["status"], "unassigned")
        for key in ("courier", "position", "destination", "eta_minutes", "updated_at"):
            self.assertIsNone(response.json()[key])
        self.assertEqual(DeliveryTracking.objects.count(), count)

    def test_coordinates_are_hidden_before_shipping_and_after_terminal_states(self):
        for status, expected in ((Order.Status.PENDING, "awaiting_shipment"),
                                 (Order.Status.PAID, "awaiting_shipment"),
                                 (Order.Status.DELIVERED, "delivered"),
                                 (Order.Status.CANCELLED, "cancelled")):
            with self.subTest(status=status):
                Order.objects.filter(pk=self.order.pk).update(status=status)
                data = self.api.get(self.url).json()
                self.assertEqual(data["status"], expected)
                self.assertIsNone(data["position"])
                self.assertIsNone(data["eta_minutes"])
                if status == Order.Status.CANCELLED:
                    self.assertIsNone(data["courier"])

    def test_assigned_courier_without_coordinates_is_awaiting_location(self):
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(courier_lat=None, courier_lng=None)
        data = self.api.get(self.url).json()
        self.assertEqual(data["status"], "awaiting_location")
        self.assertIsNone(data["position"])
        self.assertIsNotNone(data["destination"])

    def test_stale_gps_is_not_presented_as_current(self):
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(
            source="gps", position_accuracy=8,
            position_updated_at=timezone.now() - timedelta(seconds=121),
        )
        data = self.api.get(self.url).json()
        self.assertEqual(data["status"], "stale")
        self.assertIsNone(data["position"])
        self.assertIsNone(data["position_accuracy"])
        self.assertIsNone(data["eta_minutes"])
        self.assertIsNotNone(data["position_updated_at"])
        self.assertIsNotNone(data["destination"])

    def test_manual_points_keep_their_manual_source_instead_of_claiming_live_gps(self):
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(
            position_updated_at=timezone.now() - timedelta(hours=1),
        )
        data = self.api.get(self.url).json()
        self.assertEqual((data["status"], data["source"]), ("active", "manual"))

    def test_customer_cannot_write_tracking_through_read_endpoint(self):
        self.assertEqual(self.api.post(self.url, {"courier_lat": 0}, format="json").status_code, 405)
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.courier_lat, Decimal("43.240000"))


class TrackingValidationTests(TrackingFixture):
    def valid_data(self, **changes):
        return {"courier_name": "Айдос", "courier_phone": "+7 (700) 123-45-67",
                "courier_lat": "43.24", "courier_lng": "76.89", "destination_lat": "43.25",
                "destination_lng": "76.91", "eta_minutes": "12", **changes}

    def test_model_form_validates_coordinate_pairs_ranges_and_optional_eta(self):
        for changes, field in (({"courier_lat": "90.1"}, "courier_lat"),
                               ({"courier_lng": "-180.1"}, "courier_lng"),
                               ({"destination_lat": "-90.1"}, "destination_lat"),
                               ({"destination_lng": "180.1"}, "destination_lng"),
                               ({"courier_lng": ""}, "courier_lat"),
                               ({"destination_lng": ""}, "destination_lat"),
                               ({"courier_name": ""}, "courier_name"),
                               ({"courier_phone": "not-a-phone"}, "courier_phone"),
                               ({"eta_minutes": "-1"}, "eta_minutes"),
                               ({"eta_minutes": "1.5"}, "eta_minutes")):
            with self.subTest(changes=changes):
                form = DeliveryTrackingForm(self.valid_data(**changes))
                self.assertFalse(form.is_valid())
                self.assertIn(field, form.errors)
        form = DeliveryTrackingForm(self.valid_data(courier_lat="-90", courier_lng="180", eta_minutes=""))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.instance.courier_phone, "+77001234567")
        self.assertIsNone(form.instance.eta_minutes)

    def test_destination_only_is_valid_without_a_courier_assignment(self):
        form = DeliveryTrackingForm({"destination_lat": "43.25", "destination_lng": "76.91"})
        self.assertTrue(form.is_valid(), form.errors)

    def test_database_enforces_coordinate_pairing_ranges_and_assignment(self):
        for changes in ({"courier_lat": None}, {"courier_lat": 91}, {"destination_lng": 181},
                        {"courier_name": ""}, {"source": "fake"}, {"position_accuracy": -1},
                        {"share_token_hash": "hash-without-expiry"}):
            with self.subTest(changes=changes), self.assertRaises(IntegrityError), transaction.atomic():
                DeliveryTracking.objects.filter(pk=self.tracking.pk).update(**changes)


class StaffTrackingTests(TrackingValidationTests):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.admin)

    def test_staff_update_persists_and_marks_new_position_as_manual(self):
        response = self.client.post(self.staff_url, {
            "action": "update_tracking", **self.valid_data(courier_lat="43.26", courier_lng="76.92"),
        })
        self.assertRedirects(response, self.staff_url)
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.courier_lat, Decimal("43.260000"))
        self.assertEqual(self.tracking.source, "manual")
        self.assertIsNotNone(self.tracking.position_updated_at)

    def test_invalid_staff_update_shows_errors_without_saving(self):
        response = self.client.post(self.staff_url, {"action": "update_tracking", **self.valid_data(courier_lat="91")})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["tracking_form"].errors)
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.courier_lat, Decimal("43.240000"))

    def test_view_permission_does_not_allow_updates_or_sharing(self):
        self.viewer.user_permissions.add(Permission.objects.get(codename="view_order", content_type__app_label="shop"))
        self.client.force_login(self.viewer)
        self.assertEqual(self.client.get(self.staff_url).status_code, 200)
        for action in ("update_tracking", "clear_tracking", "share_courier_location", "revoke_courier_location"):
            with self.subTest(action=action):
                self.assertEqual(self.client.post(self.staff_url, {"action": action, **self.valid_data()}).status_code, 403)
        self.tracking.refresh_from_db()
        self.assertIsNone(self.tracking.share_token_hash)

    def test_tracking_update_and_sharing_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for action in ("update_tracking", "share_courier_location", "revoke_courier_location", "clear_tracking"):
            self.assertEqual(client.post(self.staff_url, {"action": action, **self.valid_data()}).status_code, 403)

    def test_finished_orders_cannot_change_assignment_or_issue_links(self):
        for status in (Order.Status.DELIVERED, Order.Status.CANCELLED):
            Order.objects.filter(pk=self.order.pk).update(status=status)
            for action in ("update_tracking", "clear_tracking", "share_courier_location"):
                with self.subTest(status=status, action=action):
                    response = self.client.post(self.staff_url, {"action": action, **self.valid_data()})
                    self.assertEqual(response.status_code, 200)
                    self.assertTrue(response.context["error"])
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.courier_name, "Айдос")
        self.assertIsNone(self.tracking.share_token_hash)

    @override_settings(PUBLIC_FRONTEND_URL="https://shop.example.test")
    def test_raw_link_is_shown_only_in_issue_response_and_uses_fragment(self):
        response = self.client.post(self.staff_url, {"action": "share_courier_location"})
        self.assertEqual(response.status_code, 200)
        link = response.context["courier_link"]
        parsed = urlsplit(link)
        self.assertEqual((parsed.scheme, parsed.netloc, parsed.path, parsed.query),
                         ("https", "shop.example.test", "/courier", ""))
        self.assertTrue(parsed.fragment)
        self.tracking.refresh_from_db()
        self.assertNotEqual(parsed.fragment, self.tracking.share_token_hash)
        self.assertNotIn(parsed.fragment, str(DeliveryTracking.objects.values().get(pk=self.tracking.pk)))
        self.assertNotContains(self.client.get(self.staff_url), parsed.fragment)

    def test_clearing_assignment_preserves_destination_and_revokes_link(self):
        token = self.share()
        self.assertRedirects(self.client.post(self.staff_url, {"action": "clear_tracking"}), self.staff_url)
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.courier_name, "")
        self.assertIsNone(self.tracking.courier_lat)
        self.assertIsNone(self.tracking.share_token_hash)
        self.assertEqual(self.tracking.destination_lat, Decimal("43.250000"))
        self.assertEqual(self.api.post(self.session_url, {"token": token}, format="json").status_code, 403)


class CourierGpsTests(TrackingFixture):
    def test_session_needs_only_the_capability_and_never_exposes_customer_address(self):
        token = self.share()
        self.api.force_authenticate(None)
        self.api.credentials(HTTP_AUTHORIZATION="Bearer expired.unrelated.token")
        response = self.api.post(self.session_url, {"token": token}, format="json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"order_id", "courier_name", "order_status", "expires_at"})
        self.assertNotIn(self.order.shipping_address, response.content.decode())
        self.assertLessEqual(self.tracking.share_expires_at or timezone.now(), timezone.now() + timedelta(hours=24))
        self.assertEqual(response["Cache-Control"], "no-store")

    def test_real_gps_updates_are_persisted_and_visible_to_the_order_owner(self):
        token = self.share()
        self.api.force_authenticate(None)
        response = self.location(token)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(set(response.json()), {"updated_at"})
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.source, "gps")
        self.assertEqual(self.tracking.position_accuracy, 8.5)
        self.assertEqual(self.tracking.courier_lat, Decimal("43.245679"))
        self.api.force_authenticate(self.owner)
        data = self.api.get(self.url).json()
        self.assertEqual((data["status"], data["source"]), ("active", "gps"))
        self.assertEqual(data["position"]["lat"], 43.245679)
        self.assertEqual(data["position_accuracy"], 8.5)
        self.assertEqual(data["position_updated_at"], response.json()["updated_at"])

    def test_invalid_missing_and_revoked_tokens_are_forbidden(self):
        for token in (None, "", "wrong", "x" * 43, ["not-a-token"]):
            with self.subTest(token=token):
                self.assertEqual(self.api.post(self.session_url, {"token": token}, format="json").status_code, 403)
                self.assertEqual(self.location(token).status_code, 403)
        old = self.share()
        current = self.share()
        self.assertNotEqual(old, current)
        self.assertEqual(self.api.post(self.session_url, {"token": old}, format="json").status_code, 403)
        self.assertEqual(self.api.post(self.session_url, {"token": current}, format="json").status_code, 200)

    def test_expired_or_finished_deliveries_reject_session_and_location(self):
        token = self.share()
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(share_expires_at=timezone.now() - timedelta(seconds=1))
        self.assertEqual(self.api.post(self.session_url, {"token": token}, format="json").status_code, 410)
        self.assertEqual(self.location(token).status_code, 410)
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(share_expires_at=timezone.now() + timedelta(hours=1))
        for status in (Order.Status.PENDING, Order.Status.PAID, Order.Status.CANCELLED, Order.Status.DELIVERED):
            with self.subTest(status=status):
                Order.objects.filter(pk=self.order.pk).update(status=status)
                self.assertEqual(self.api.post(self.session_url, {"token": token}, format="json").status_code, 410)
                self.assertEqual(self.location(token).status_code, 410)

    def test_partial_out_of_range_nonfinite_and_boolean_coordinates_are_rejected(self):
        token = self.share()
        invalid = ({"latitude": 90.1}, {"latitude": -90.1}, {"longitude": 180.1},
                   {"longitude": -180.1}, {"latitude": True}, {"longitude": None},
                   {"latitude": "NaN"}, {"longitude": "Infinity"}, {"accuracy": -1},
                   {"accuracy": "NaN"}, {"accuracy": True})
        for changes in invalid:
            with self.subTest(changes=changes):
                self.assertEqual(self.location(token, **changes).status_code, 400)
        self.assertEqual(self.api.post(self.location_url, {"token": token, "latitude": 43}, format="json").status_code, 400)
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.source, "manual")
        self.assertEqual(self.tracking.courier_lat, Decimal("43.240000"))

    def test_updates_are_rate_limited_without_rewriting_last_position(self):
        token = self.share()
        self.assertEqual(self.location(token).status_code, 200)
        response = self.location(token, latitude=1)
        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response)
        self.tracking.refresh_from_db()
        self.assertEqual(self.tracking.courier_lat, Decimal("43.245679"))
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(position_updated_at=timezone.now() - timedelta(seconds=4))
        self.assertEqual(self.location(token, latitude=1).status_code, 200)

    def test_revoke_and_assignment_change_immediately_disable_old_phone(self):
        token = self.share()
        self.assertEqual(self.location(token).status_code, 200)
        self.client.force_login(self.admin)
        self.assertRedirects(self.client.post(self.staff_url, {"action": "revoke_courier_location"}), self.staff_url)
        self.assertEqual(self.location(token).status_code, 403)
        self.assertIsNone(self.api.get(self.url).json()["position"])
