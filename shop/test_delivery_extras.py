"""Automatic delivery point from the order address, and the "courier is nearby" notification."""
import io
import json
from datetime import timedelta
from unittest import mock

from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from . import geocoding
from .models import DeliveryTracking, Notification, Order
from .test_tracking import TrackingFixture
from .tracking import update_tracking


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@override_settings(NOMINATIM_ENABLED=True, NOMINATIM_URL="https://geo.example.test/search")
class GeocodeTests(TrackingFixture):
    def setUp(self):
        super().setUp()
        cache.clear()
        geocoding._last_call = 0.0

    def respond(self, payload):
        return mock.patch("shop.geocoding.urllib.request.urlopen",
                          return_value=_Response(json.dumps(payload).encode()))

    def test_found_address_is_cached(self):
        with self.respond([{"lat": "43.2380001", "lon": "76.9450009"}]) as urlopen, \
                mock.patch("shop.geocoding.time.sleep"):
            self.assertEqual(geocoding.geocode("Алматы, пр. Абая 10"), (43.238, 76.945001))
            self.assertEqual(geocoding.geocode("  алматы, ПР. Абая 10 "), (43.238, 76.945001))
        self.assertEqual(urlopen.call_count, 1)
        sent = urlopen.call_args.args[0]
        self.assertIn("countrycodes=kz", sent.full_url)
        self.assertTrue(sent.get_header("User-agent"))

    def test_unknown_bad_or_offline_returns_none(self):
        with self.respond([]):
            self.assertIsNone(geocoding.geocode("Nowhere 1"))
        with self.respond([{"lat": "999", "lon": "1"}]):
            self.assertIsNone(geocoding.geocode("Broken 2"))
        with mock.patch("shop.geocoding.urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertIsNone(geocoding.geocode("Offline 3"))
        self.assertIsNone(geocoding.geocode(""))

    @override_settings(NOMINATIM_ENABLED=False)
    def test_disabled_never_calls_the_internet(self):
        with mock.patch("shop.geocoding.urllib.request.urlopen") as urlopen:
            self.assertIsNone(geocoding.geocode("Алматы"))
        urlopen.assert_not_called()

    def test_address_is_cleaned_before_lookup(self):
        self.assertEqual(geocoding.address_variants("г. Алматы, пр. Абая 10, кв. 25"), ["Алматы, проспект Абая 10"])
        self.assertEqual(geocoding.address_variants("Алматы, ул. Толе би 59, подъезд 2"), ["Алматы, улица Толе би 59"])
        self.assertEqual(geocoding.address_variants("Almaty, Abay Ave 10, apartment 2"), ["Almaty, Abay Ave 10"])
        self.assertEqual(geocoding.address_variants("Астана, мкр. Самал 5, корпус 3"),
                         ["Астана, микрорайон Самал 5, корпус 3", "Астана, микрорайон Самал 5"])

    def test_shorter_address_is_tried_when_the_full_one_is_unknown(self):
        answers = [_Response(b"[]"), _Response(b'[{"lat": "51.1", "lon": "71.4"}]')]
        with mock.patch("shop.geocoding.urllib.request.urlopen", side_effect=answers) as urlopen, \
                mock.patch("shop.geocoding.time.sleep"):
            self.assertEqual(geocoding.geocode("Астана, мкр. Самал 5, корпус 3"), (51.1, 71.4))
        self.assertEqual(urlopen.call_count, 2)

    def test_offline_result_is_not_cached(self):
        with mock.patch("shop.geocoding.urllib.request.urlopen", side_effect=OSError("offline")):
            self.assertIsNone(geocoding.geocode("Алматы, пр. Абая 1"))
        with self.respond([{"lat": "43.2", "lon": "76.9"}]), mock.patch("shop.geocoding.time.sleep"):
            self.assertEqual(geocoding.geocode("Алматы, пр. Абая 1"), (43.2, 76.9))

    def test_distance(self):
        self.assertAlmostEqual(geocoding.distance_m(43.238, 76.945, 43.238, 76.945), 0)
        self.assertAlmostEqual(geocoding.distance_m(43.238, 76.945, 43.247, 76.945), 1000, delta=10)


class AutoDestinationTests(TrackingFixture):
    def form_data(self, **changes):
        data = {"courier_name": "Айдос", "courier_phone": "+77001234567", "courier_lat": "", "courier_lng": "",
                "destination_lat": "", "destination_lng": "", "eta_minutes": ""}
        data.update(changes)
        return data

    def test_empty_destination_is_filled_from_the_address(self):
        with mock.patch("shop.tracking.geocode", return_value=(43.2, 76.9)) as lookup:
            form = update_tracking(self.order, self.form_data())
        lookup.assert_called_once_with(self.order.shipping_address)
        self.assertTrue(form.geocoded)
        self.tracking.refresh_from_db()
        self.assertEqual((float(self.tracking.destination_lat), float(self.tracking.destination_lng)), (43.2, 76.9))

    def test_typed_destination_is_kept_and_not_looked_up(self):
        with mock.patch("shop.tracking.geocode") as lookup:
            form = update_tracking(self.order, self.form_data(destination_lat="43.1", destination_lng="76.8"))
        lookup.assert_not_called()
        self.assertIsNone(form.geocoded)

    def test_not_found_is_reported_to_staff(self):
        self.client.force_login(self.admin)
        with mock.patch("shop.tracking.geocode", return_value=None):
            response = self.client.post(reverse("staff_order_detail", args=[self.order.pk]),
                                        {"action": "update_tracking", **self.form_data()}, follow=True)
        self.assertContains(response, "Адрес не удалось найти на карте автоматически")


class CourierNearbyTests(TrackingFixture):
    # destination in the fixture: 43.25, 76.91
    def report(self, token, lat, lng):
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(
            position_updated_at=timezone.now() - timedelta(seconds=10))
        return self.location(token, latitude=lat, longitude=lng)

    def nearby_notes(self):
        return Notification.objects.filter(user=self.owner, order=self.order, link__endswith="/tracking")

    def test_customer_is_told_once_when_the_courier_is_close(self):
        token = self.share()
        self.api.force_authenticate(None)
        self.assertEqual(self.report(token, 43.20, 76.91).status_code, 200)     # ~5.5 km away
        self.assertFalse(self.nearby_notes().exists())
        self.assertEqual(self.report(token, 43.2470, 76.91).status_code, 200)   # ~330 m away
        self.assertEqual(self.nearby_notes().count(), 1)
        note = self.nearby_notes().get()
        self.assertIn(str(self.order.pk), note.message_ru)
        self.assertEqual(note.link, f"/orders/{self.order.pk}/tracking")
        self.report(token, 43.2495, 76.91)                                       # still close: no repeat
        self.assertEqual(self.nearby_notes().count(), 1)

    def test_no_notification_without_a_destination(self):
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(destination_lat=None, destination_lng=None)
        token = self.share()
        self.api.force_authenticate(None)
        self.report(token, 43.25, 76.91)
        self.assertFalse(self.nearby_notes().exists())

    def test_new_courier_can_trigger_it_again(self):
        DeliveryTracking.objects.filter(pk=self.tracking.pk).update(near_notified_at=timezone.now())
        with mock.patch("shop.tracking.geocode"):
            update_tracking(self.order, {"courier_name": "Ерлан", "courier_phone": "+77009998877",
                                         "courier_lat": "", "courier_lng": "", "destination_lat": "43.25",
                                         "destination_lng": "76.91", "eta_minutes": ""})
        self.tracking.refresh_from_db()
        self.assertIsNone(self.tracking.near_notified_at)
        self.assertEqual(Order.objects.get(pk=self.order.pk).status, Order.Status.SHIPPED)
