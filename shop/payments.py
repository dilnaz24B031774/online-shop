"""
Card payments.

  * the full card number and CVC are NEVER saved in our database;
  * we keep only the card type (Visa, Mastercard, Mir...) and the last 4 digits,
    plus the "reference" the payment provider returns;
  * the number is checked with the Luhn algorithm, the expiry date must be in the future.

Sandbox cards:
  4242 4242 4242 4242  -> payment approved
  4000 0000 0000 0002  -> payment declined (not enough money)
  any other correct number -> approved
"""
import re
import secrets
from dataclasses import dataclass

from django.utils import timezone

DECLINED_CARDS = {"4000000000000002": "Not enough money on the card."}


class CardInvalid(Exception):
    """Wrong card data typed by the customer (nothing is saved)."""

    def __init__(self, field, message):
        self.field = field
        super().__init__(message)


@dataclass
class ChargeResult:
    approved: bool
    brand: str
    last4: str
    reference: str
    reason: str = ""


def luhn_ok(number: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(number)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def card_brand(number: str) -> str:
    if number.startswith("4"):
        return "visa"
    if re.match(r"^(5[1-5]|222[1-9]|22[3-9]\d|2[3-6]\d\d|27[01]\d|2720)", number):
        return "mastercard"
    if re.match(r"^220[0-4]", number):
        return "mir"
    if re.match(r"^3[47]", number):
        return "amex"
    return "card"


def validate_card(card: dict) -> tuple[str, str]:
    """Returns (clean number, brand) or raises CardInvalid."""
    if not isinstance(card, dict):
        raise CardInvalid("number", "Enter the card details.")
    number = re.sub(r"[\s-]", "", str(card.get("number", "")))
    if not number.isdigit() or not 13 <= len(number) <= 19 or not luhn_ok(number):
        raise CardInvalid("number", "The card number is not correct.")
    brand = card_brand(number)

    holder = str(card.get("holder", "")).strip()
    if len(holder) < 2 or not re.fullmatch(r"[A-Za-zА-Яа-яЁёӘәҒғҚқҢңӨөҰұҮүҺһІі .'-]+", holder):
        raise CardInvalid("holder", "Enter the name as it is written on the card.")

    try:
        month, year = int(card.get("exp_month")), int(card.get("exp_year"))
    except (TypeError, ValueError):
        raise CardInvalid("expiry", "Enter the expiry date MM/YY.")
    if year < 100:
        year += 2000
    today = timezone.localdate()
    if not 1 <= month <= 12 or (year, month) < (today.year, today.month) or year > today.year + 20:
        raise CardInvalid("expiry", "The card has expired or the date is not correct.")

    cvc = str(card.get("cvc", ""))
    if not cvc.isdigit() or len(cvc) != (4 if brand == "amex" else 3):
        raise CardInvalid("cvc", "CVC is 3 digits on the back of the card.")
    return number, brand


def charge(card: dict, amount) -> ChargeResult:
    """Charge the card through the payment provider. Only brand + last 4 digits leave this function."""
    number, brand = validate_card(card)
    reference = "PAY-" + secrets.token_hex(6).upper()
    reason = DECLINED_CARDS.get(number, "")
    return ChargeResult(approved=not reason, brand=brand, last4=number[-4:], reference=reference, reason=reason)


def card_expiry(card: dict) -> tuple[int, int]:
    """(month, 4-digit year) of an already validated card."""
    month, year = int(card.get("exp_month")), int(card.get("exp_year"))
    return month, (year + 2000 if year < 100 else year)


def new_token() -> str:
    """The bank gives the shop a random token instead of the card number."""
    return "tok_" + secrets.token_hex(12)


def charge_token(saved_card, cvc: str, amount) -> ChargeResult:
    """Pay with a saved card: the shop sends only the TOKEN (+ CVC typed again by the customer)."""
    cvc = str(cvc or "")
    if not cvc.isdigit() or len(cvc) != (4 if saved_card.brand == "amex" else 3):
        raise CardInvalid("cvc", "CVC is 3 digits on the back of the card.")
    today = timezone.localdate()
    if (saved_card.exp_year, saved_card.exp_month) < (today.year, today.month):
        raise CardInvalid("saved_card", "This card has expired. Please add a new card.")
    return ChargeResult(approved=True, brand=saved_card.brand, last4=saved_card.last4,
                        reference="PAY-" + secrets.token_hex(6).upper())
