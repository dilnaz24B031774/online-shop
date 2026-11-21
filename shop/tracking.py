"""Private order tracking, staff updates, and revocable courier GPS links."""
import math
import os
import re
import secrets
from collections.abc import Mapping
from datetime import timedelta
from urllib.parse import urlsplit

from django import forms
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac
from rest_framework import serializers
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.exceptions import APIException
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from .geocoding import distance_m, geocode
from .models import DeliveryTracking, Notification, Order


class DeliveryTrackingForm(forms.ModelForm):
    class Meta:
        model = DeliveryTracking
        fields = (
            "courier_name", "courier_phone", "courier_lat", "courier_lng",
            "destination_lat", "destination_lng", "eta_minutes",
        )
        labels = {
            "courier_name": "Имя курьера", "courier_phone": "Телефон курьера",
            "courier_lat": "Широта курьера", "courier_lng": "Долгота курьера",
            "destination_lat": "Широта адреса доставки", "destination_lng": "Долгота адреса доставки",
            "eta_minutes": "До прибытия, минут",
        }
        help_texts = {
            "courier_name": "Имя и контакты назначенного на этот заказ курьера.",
            "courier_lat": "От −90 до 90. Обе координаты вводятся вместе.",
            "courier_lng": "От −180 до 180. Пустые поля означают, что местоположение ещё не сообщено.",
            "destination_lat": "Координаты точки доставки, соответствующей адресу заказа.",
            "eta_minutes": "Сообщённая курьером оценка; можно оставить пустым.",
        }
        widgets = {
            "courier_lat": forms.NumberInput(attrs={"min": -90, "max": 90, "step": "0.000001"}),
            "courier_lng": forms.NumberInput(attrs={"min": -180, "max": 180, "step": "0.000001"}),
            "destination_lat": forms.NumberInput(attrs={"min": -90, "max": 90, "step": "0.000001"}),
            "destination_lng": forms.NumberInput(attrs={"min": -180, "max": 180, "step": "0.000001"}),
            "eta_minutes": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }


def tracking_payload(order):
    tracking = getattr(order, "delivery_tracking", None)
    assigned = tracking is not None and bool(tracking.courier_name.strip())
    coordinates = assigned and tracking.courier_lat is not None and tracking.courier_lng is not None
    stale = coordinates and tracking.source == DeliveryTracking.Source.GPS and (
        tracking.position_updated_at is None
        or (timezone.now() - tracking.position_updated_at).total_seconds() > 120
    )
    if order.status == Order.Status.CANCELLED:
        state = "cancelled"
    elif order.status == Order.Status.DELIVERED:
        state = "delivered"
    elif not assigned:
        state = "unassigned"
    elif order.status != Order.Status.SHIPPED:
        state = "awaiting_shipment"
    elif not coordinates:
        state = "awaiting_location"
    elif stale:
        state = "stale"
    else:
        state = "active"
    active = state == "active"
    courier = ({"name": tracking.courier_name, "phone": tracking.courier_phone}
               if assigned and state != "cancelled" else None)
    destination = None
    if tracking is not None and tracking.destination_lat is not None and tracking.destination_lng is not None:
        destination = {"lat": float(tracking.destination_lat), "lng": float(tracking.destination_lng)}
    return {
        "order_id": order.pk, "order_status": order.status, "shipping_address": order.shipping_address,
        "status": state, "source": tracking.source if tracking is not None else DeliveryTracking.Source.MANUAL,
        "courier": courier,
        "position": {"lat": float(tracking.courier_lat), "lng": float(tracking.courier_lng)} if active else None,
        "destination": destination,
        "eta_minutes": tracking.eta_minutes if active else None,
        "position_accuracy": tracking.position_accuracy if active else None,
        "position_updated_at": tracking.position_updated_at if tracking is not None else None,
        "updated_at": tracking.updated_at if tracking is not None else None,
    }


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def order_tracking(request, pk):
    orders = Order.objects.select_related("delivery_tracking")
    can_view_all = request.user.is_staff and any(request.user.has_perm(f"shop.{action}_order")
                                               for action in ("view", "change"))
    if not can_view_all:
        orders = orders.filter(user=request.user)
    order = get_object_or_404(orders, pk=pk)
    response = Response(tracking_payload(order))
    response["Cache-Control"] = "private, no-store"
    response["Vary"] = "Authorization, Cookie"
    return response


def _editable_order(order):
    current = Order.objects.select_for_update().get(pk=order.pk)
    if current.status in (Order.Status.CANCELLED, Order.Status.DELIVERED):
        raise ValidationError("Доставка завершена или отменена. Изменить данные курьера нельзя.")
    return current


def update_tracking(order, data):
    """Save the courier form; an empty destination is looked up from the order address first.

    The lookup calls the internet, so it runs before the order row is locked.
    form.geocoded: True = found automatically, False = not found, None = not needed.
    """
    geocoded = None
    blank = lambda name: not str(data.get(name, "") or "").strip()
    if blank("destination_lat") and blank("destination_lng"):
        point = geocode(order.shipping_address)
        geocoded = point is not None
        if point:
            data = data.copy()
            data["destination_lat"], data["destination_lng"] = str(point[0]), str(point[1])
    form = _save_tracking(order, data)
    form.geocoded = geocoded if form.is_valid() else None
    return form


@transaction.atomic
def _save_tracking(order, data):
    """Serialize with fulfillment/cancellation and validate before persisting."""
    current = _editable_order(order)
    tracking = DeliveryTracking.objects.filter(order=current).first() or DeliveryTracking(order=current)
    form = DeliveryTrackingForm(data, instance=tracking)
    if form.is_valid():
        tracking = form.save(commit=False)
        position_changed = any(field in form.changed_data for field in ("courier_lat", "courier_lng"))
        assignment_changed = any(field in form.changed_data for field in ("courier_name", "courier_phone"))
        if assignment_changed or any(f in form.changed_data for f in ("destination_lat", "destination_lng")):
            tracking.near_notified_at = None
        if assignment_changed:
            tracking.share_token_hash = tracking.share_expires_at = None
            if not position_changed:
                tracking.courier_lat = tracking.courier_lng = None
                position_changed = True
        if position_changed:
            tracking.source = DeliveryTracking.Source.MANUAL
            tracking.position_accuracy = None
            tracking.position_updated_at = timezone.now() if tracking.courier_lat is not None else None
        tracking.save()
    return form


@transaction.atomic
def clear_assignment(order):
    current = _editable_order(order)
    tracking = DeliveryTracking.objects.filter(order=current).first()
    if tracking is None:
        return
    tracking.courier_name = tracking.courier_phone = ""
    tracking.courier_lat = tracking.courier_lng = tracking.eta_minutes = None
    tracking.position_accuracy = tracking.position_updated_at = None
    tracking.share_token_hash = tracking.share_expires_at = tracking.near_notified_at = None
    tracking.source = DeliveryTracking.Source.MANUAL
    tracking.save(update_fields=("courier_name", "courier_phone", "courier_lat", "courier_lng",
                                 "eta_minutes", "position_accuracy", "position_updated_at",
                                 "share_token_hash", "share_expires_at", "near_notified_at",
                                 "source", "updated_at"))


def _token_digest(raw):
    if not isinstance(raw, str) or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", raw):
        raise SharingLinkInvalid()
    return salted_hmac("shop.courier.gps", raw, algorithm="sha256").hexdigest()


@transaction.atomic
def issue_sharing_token(order):
    """Return a new one-use-display token; rotation immediately revokes the old link."""
    current = Order.objects.select_for_update().get(pk=order.pk)
    tracking = DeliveryTracking.objects.filter(order=current).first()
    if current.status != Order.Status.SHIPPED or tracking is None or not tracking.courier_name.strip():
        raise ValidationError("Ссылка доступна после передачи заказа в доставку и назначения курьера.")
    raw = secrets.token_urlsafe(32)
    tracking.share_token_hash = _token_digest(raw)
    tracking.share_expires_at = timezone.now() + timedelta(hours=24)
    if tracking.source == DeliveryTracking.Source.GPS:
        tracking.courier_lat = tracking.courier_lng = tracking.eta_minutes = None
        tracking.position_accuracy = tracking.position_updated_at = None
        tracking.source = DeliveryTracking.Source.MANUAL
    tracking.save()
    return raw, tracking.share_expires_at


@transaction.atomic
def revoke_sharing_token(order):
    # Revocation is always available, even after the order has finished.
    current = Order.objects.select_for_update().get(pk=order.pk)
    tracking = DeliveryTracking.objects.filter(order=current).first()
    if tracking is None:
        return
    tracking.share_token_hash = tracking.share_expires_at = None
    if tracking.source == DeliveryTracking.Source.GPS:
        tracking.courier_lat = tracking.courier_lng = tracking.eta_minutes = None
        tracking.position_accuracy = tracking.position_updated_at = None
        tracking.source = DeliveryTracking.Source.MANUAL
    tracking.save()


def sharing_url(request, raw):
    base = getattr(settings, "PUBLIC_FRONTEND_URL", "") or os.environ.get("PUBLIC_FRONTEND_URL", "")
    if not base:
        host = urlsplit(request.build_absolute_uri("/")).hostname
        host = f"[{host}]" if ":" in host else host
        base = f"{request.scheme}://{host}:4200"
    parsed = urlsplit(base)
    if parsed.scheme not in ("http", "https") or not parsed.netloc or parsed.username or parsed.password:
        raise ValidationError("Проверьте адрес сайта PUBLIC_FRONTEND_URL.")
    return f"{base.rstrip('/')}/courier#{raw}"


class SharingLinkInvalid(APIException):
    status_code = 403
    default_detail = "Ссылка курьера недействительна или была отключена."
    default_code = "invalid_courier_link"


class SharingLinkInactive(APIException):
    status_code = 410
    default_detail = "Срок ссылки истёк или доставка больше не активна."
    default_code = "inactive_courier_link"


def _check_shared_tracking(tracking, digest):
    if tracking is None or not constant_time_compare(tracking.share_token_hash or "", digest):
        raise SharingLinkInvalid()
    if (tracking.share_expires_at is None or tracking.share_expires_at <= timezone.now()
            or tracking.order.status != Order.Status.SHIPPED or not tracking.courier_name.strip()):
        raise SharingLinkInactive()


def _shared_tracking(data):
    digest = _token_digest(data.get("token") if isinstance(data, Mapping) else None)
    tracking = DeliveryTracking.objects.select_related("order").filter(share_token_hash=digest).first()
    _check_shared_tracking(tracking, digest)
    return tracking, digest


class FiniteFloatField(serializers.FloatField):
    def to_internal_value(self, data):
        if isinstance(data, bool):
            self.fail("invalid")
        value = super().to_internal_value(data)
        if not math.isfinite(value):
            self.fail("invalid")
        return value


class CourierLocationSerializer(serializers.Serializer):
    latitude = FiniteFloatField(min_value=-90, max_value=90)
    longitude = FiniteFloatField(min_value=-180, max_value=180)
    accuracy = FiniteFloatField(min_value=0, required=False, allow_null=True, default=None)


NEAR_METERS = 500


def notify_if_near(tracking, order):
    """Tell the customer once per delivery that the courier is within NEAR_METERS of the address.
    Called inside the locked transaction, so two GPS reports cannot both send it."""
    if (tracking.near_notified_at is not None or tracking.destination_lat is None
            or tracking.destination_lng is None or tracking.courier_lat is None or tracking.courier_lng is None):
        return False
    if distance_m(tracking.courier_lat, tracking.courier_lng,
                  tracking.destination_lat, tracking.destination_lng) > NEAR_METERS:
        return False
    tracking.near_notified_at = timezone.now()
    tracking.save(update_fields=("near_notified_at",))
    Notification.objects.create(
        user_id=order.user_id, order=order, kind=Notification.Kind.ORDER,
        link=f"/orders/{order.pk}/tracking",
        message=f"Your courier is nearby — order #{order.pk} will arrive in a few minutes.",
        message_ru=f"Курьер уже рядом — заказ №{order.pk} будет у вас через несколько минут.",
        message_kk=f"Курьер жақын жерде — №{order.pk} тапсырыс бірнеше минутта жетеді.",
    )
    return True


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def courier_session(request):
    tracking, _ = _shared_tracking(request.data)
    response = Response({"order_id": tracking.order_id, "courier_name": tracking.courier_name,
                         "order_status": tracking.order.status, "expires_at": tracking.share_expires_at})
    response["Cache-Control"] = "no-store"
    return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([AllowAny])
def courier_location(request):
    tracking, digest = _shared_tracking(request.data)
    location = CourierLocationSerializer(data=request.data)
    location.is_valid(raise_exception=True)
    with transaction.atomic():
        # Match the lock order used by staff assignment and fulfillment.
        order = Order.objects.select_for_update().get(pk=tracking.order_id)
        tracking = DeliveryTracking.objects.select_for_update().get(pk=tracking.pk)
        tracking.order = order
        _check_shared_tracking(tracking, digest)
        now = timezone.now()
        if tracking.source == DeliveryTracking.Source.GPS and tracking.position_updated_at is not None:
            elapsed = (now - tracking.position_updated_at).total_seconds()
            if elapsed < 3:
                response = Response({"detail": "Отправляйте координаты не чаще одного раза в 3 секунды."},
                                    status=429, headers={"Retry-After": str(max(1, math.ceil(3 - elapsed)))})
                response["Cache-Control"] = "no-store"
                return response
        tracking.courier_lat = location.validated_data["latitude"]
        tracking.courier_lng = location.validated_data["longitude"]
        tracking.position_accuracy = location.validated_data["accuracy"]
        tracking.position_updated_at = now
        tracking.source = DeliveryTracking.Source.GPS
        tracking.save(update_fields=("courier_lat", "courier_lng", "position_accuracy", "position_updated_at",
                                     "source", "updated_at"))
        notify_if_near(tracking, order)
    response = Response({"updated_at": tracking.position_updated_at})
    response["Cache-Control"] = "no-store"
    return response
