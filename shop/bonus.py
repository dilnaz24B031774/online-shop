"""Bonus programme: paid orders earn treats, the customer feeds the mascots, the mascots give merch.

Rules (change them here, everything else follows):
  * every full $10 of a paid order        -> 1 kurt          (1 point)
  * every full $50 of a paid order        -> 1 Nauryz kozhe  (5 points)
  * treats are given to Aisulu or Altai; each mascot has its own goals and gifts.
Treats are counted from paid orders every time, so a refund or cancellation takes them back.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from rest_framework import serializers, status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Address, BonusFeeding, GiftClaim, Notification, Order, Payment, User

KURT_EVERY = Decimal("10")
KOZHE_EVERY = Decimal("50")
POINTS = {"kurt": 1, "kozhe": 5}
CHARACTERS = ("aisulu", "altai")

# (points needed, gift code, name for staff)
GIFTS = {
    "aisulu": [(10, "aisulu_stickers", "Стикерпак с Айсұлу"), (30, "aisulu_keychain", "Брелок Айсұлу"),
               (60, "aisulu_tote", "Шоппер SaudaGo с орнаментом"), (100, "aisulu_hoodie", "Худи SaudaGo")],
    "altai": [(10, "altai_badge", "Значок с Алтаем"), (30, "altai_mug", "Кружка Алтай"),
              (60, "altai_cap", "Кепка SaudaGo"), (100, "altai_tshirt", "Футболка SaudaGo")],
}
GIFT_BY_CODE = {code: (character, need, name) for character, gifts in GIFTS.items() for need, code, name in gifts}


def earned_treats(user):
    """Treats earned by paid orders, net of refunds."""
    kurt = kozhe = 0
    orders = (Order.objects.filter(user=user, payment__status=Payment.Status.PAID,
                                   status__in=(Order.Status.PAID, Order.Status.SHIPPED, Order.Status.DELIVERED))
              .values_list("total_amount", "payment__refunded_amount"))
    for total, refunded in orders:
        net = (total or Decimal("0")) - (refunded or Decimal("0"))
        if net > 0:
            kurt += int(net // KURT_EVERY)
            kozhe += int(net // KOZHE_EVERY)
    return {"kurt": kurt, "kozhe": kozhe}


def fed_treats(user):
    fed = {c: {"kurt": 0, "kozhe": 0} for c in CHARACTERS}
    for row in BonusFeeding.objects.filter(user=user).values("character", "treat").annotate(n=Sum("quantity")):
        fed[row["character"]][row["treat"]] = row["n"]
    return fed


def bonus_state(user):
    earned, fed = earned_treats(user), fed_treats(user)
    given = {t: sum(fed[c][t] for c in CHARACTERS) for t in POINTS}
    available = {t: max(0, earned[t] - given[t]) for t in POINTS}
    claims = {c.gift: c for c in GiftClaim.objects.filter(user=user)}
    characters = []
    for character in CHARACTERS:
        points = sum(fed[character][t] * POINTS[t] for t in POINTS)
        gifts = []
        for need, code, _ in GIFTS[character]:
            claim = claims.get(code)
            gifts.append({"code": code, "points": need, "unlocked": points >= need,
                          "status": claim.status if claim else None,
                          "claimed_at": claim.created_at if claim else None})
        next_goal = next((g["points"] for g in gifts if not g["unlocked"]), None)
        characters.append({"id": character, "points": points, "fed": fed[character], "next_goal": next_goal,
                           "gifts": gifts})
    return {"earned": earned, "available": available, "characters": characters,
            "rules": {"kurt_every": str(KURT_EVERY), "kozhe_every": str(KOZHE_EVERY), "points": POINTS}}


class FeedSerializer(serializers.Serializer):
    character = serializers.ChoiceField(choices=CHARACTERS)
    treat = serializers.ChoiceField(choices=tuple(POINTS))
    quantity = serializers.IntegerField(min_value=1, max_value=1000)


class ClaimSerializer(serializers.Serializer):
    gift = serializers.ChoiceField(choices=tuple(GIFT_BY_CODE))
    address = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")


def _no_store(response):
    response["Cache-Control"] = "private, no-store"
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def bonus(request):
    return _no_store(Response(bonus_state(request.user)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bonus_feed(request):
    data = FeedSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    character, treat, quantity = (data.validated_data[k] for k in ("character", "treat", "quantity"))
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)      # one feeding at a time per customer
        if quantity > bonus_state(request.user)["available"][treat]:
            return _no_store(Response({"detail": "not_enough_treats"}, status=status.HTTP_400_BAD_REQUEST))
        BonusFeeding.objects.create(user=request.user, character=character, treat=treat, quantity=quantity)
    return _no_store(Response(bonus_state(request.user)))


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def bonus_claim(request):
    data = ClaimSerializer(data=request.data)
    data.is_valid(raise_exception=True)
    code = data.validated_data["gift"]
    character, need, _ = GIFT_BY_CODE[code]
    address = data.validated_data["address"].strip()
    if not address:
        default = Address.objects.filter(user=request.user).order_by("-is_default", "-pk").first()
        address = f"{default.city}, {default.street}" if default else ""
    if not address:
        return _no_store(Response({"detail": "address_required"}, status=status.HTTP_400_BAD_REQUEST))
    with transaction.atomic():
        User.objects.select_for_update().get(pk=request.user.pk)
        points = next(c["points"] for c in bonus_state(request.user)["characters"] if c["id"] == character)
        if points < need:
            return _no_store(Response({"detail": "gift_locked"}, status=status.HTTP_400_BAD_REQUEST))
        if GiftClaim.objects.filter(user=request.user, gift=code).exists():
            return _no_store(Response({"detail": "already_claimed"}, status=status.HTTP_409_CONFLICT))
        GiftClaim.objects.create(user=request.user, gift=code, address=address[:255])
    return _no_store(Response(bonus_state(request.user), status=status.HTTP_201_CREATED))


# ---------- staff: send out the merch ----------

def _staff_check(request):
    from django.core.exceptions import PermissionDenied
    if not (request.user.is_superuser or request.user.has_perm("shop.change_order")):
        raise PermissionDenied


@require_http_methods(["GET", "HEAD", "POST"])
def staff_gifts(request):
    _staff_check(request)
    if request.method == "POST":
        claim = get_object_or_404(GiftClaim.objects.select_related("user"), pk=request.POST.get("claim"),
                                  status=GiftClaim.Status.REQUESTED)
        claim.status, claim.sent_at = GiftClaim.Status.SENT, timezone.now()
        claim.save(update_fields=("status", "sent_at"))
        name = GIFT_BY_CODE.get(claim.gift, (None, None, claim.gift))[2]
        Notification.objects.create(
            user=claim.user, kind=Notification.Kind.PROMO, link="/bonus",
            message="Your SaudaGo gift is on its way! 🎁", message_ru=f"Ваш подарок «{name}» отправлен! 🎁",
            message_kk=f"«{name}» сыйлығыңыз жіберілді! 🎁")
        from django.contrib import messages
        messages.success(request, f"Подарок «{name}» отмечен как отправленный, покупатель получил уведомление.")
        return redirect("staff_gifts")
    show = request.GET.get("show", "requested")
    claims = GiftClaim.objects.select_related("user").order_by("status", "-created_at")
    if show != "all":
        claims = claims.filter(status=GiftClaim.Status.REQUESTED)
    rows = [{"claim": c, "name": GIFT_BY_CODE.get(c.gift, (None, None, c.gift))[2],
             "character": dict(BonusFeeding.Character.choices).get(GIFT_BY_CODE.get(c.gift, ("",))[0], "")}
            for c in claims[:300]]
    return render(request, "shop/staff_gifts.html", {
        "rows": rows, "show": show, "active_section": "gifts",
        "waiting": GiftClaim.objects.filter(status=GiftClaim.Status.REQUESTED).count(),
    })
