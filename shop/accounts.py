"""Account identity rules: username format, phone format, login by username or email."""
import random
import re

from django.db.models.functions import Lower

USERNAME_MIN, USERNAME_MAX = 3, 30
USERNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,28}[A-Za-z0-9]$")
RESERVED = {"admin", "administrator", "root", "support", "help", "staff", "manager", "sauda", "saudago",
            "api", "system", "moderator", "official", "null", "undefined"}


class UsernameError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


MESSAGES = {
    "length": f"Username must be {USERNAME_MIN}–{USERNAME_MAX} characters long.",
    "format": "Use Latin letters, digits and . _ - (start and end with a letter or digit).",
    "reserved": "This username is reserved.",
    "taken": "This username is already taken.",
}


def check_username(value, exclude_pk=None):
    """Raises UsernameError if the username cannot be used."""
    from .models import User
    value = (value or "").strip()
    if not USERNAME_MIN <= len(value) <= USERNAME_MAX:
        raise UsernameError("length", MESSAGES["length"])
    if not USERNAME_RE.match(value) or ".." in value:
        raise UsernameError("format", MESSAGES["format"])
    if value.lower() in RESERVED:
        raise UsernameError("reserved", MESSAGES["reserved"])
    taken = User.objects.filter(username__iexact=value)
    if exclude_pk:
        taken = taken.exclude(pk=exclude_pk)
    if taken.exists():
        raise UsernameError("taken", MESSAGES["taken"])
    return value


def suggest_usernames(base, count=3):
    """Free variants: aigerim -> aigerim_k, aigerim2026, aigerim.7."""
    from .models import User
    stem = re.sub(r"[^A-Za-z0-9._-]", "", base or "").strip("._-")[:22] or "user"
    if len(stem) < USERNAME_MIN:
        stem = (stem + "user")[:USERNAME_MAX]
    rnd = random.Random(stem.lower())
    candidates = [f"{stem}{rnd.randint(10, 99)}", f"{stem}_{rnd.choice('abcdefghkmnprstz')}",
                  f"{stem}.{rnd.randint(2, 9)}", f"{stem}2026", f"{stem}_{rnd.randint(100, 999)}",
                  f"the.{stem}", f"{stem}_kz"]
    taken = set(User.objects.annotate(l=Lower("username"))
                .filter(l__in=[c.lower() for c in candidates]).values_list("l", flat=True))
    free = []
    for c in candidates:
        if c.lower() not in taken and USERNAME_RE.match(c) and c.lower() not in RESERVED:
            free.append(c)
        if len(free) == count:
            break
    return free


def normalize_phone(value):
    """'8 701 111-11-11' -> '+77011111111'. Returns '' for empty, raises ValueError if wrong."""
    value = (value or "").strip()
    if not value:
        return ""
    if not re.fullmatch(r"\+?[0-9 ()-]+", value):
        raise ValueError
    digits = re.sub(r"\D", "", value)
    if len(digits) == 11 and digits.startswith("8"):      # Kazakhstan: 8 7xx -> +7 7xx
        digits = "7" + digits[1:]
    if len(digits) == 10 and digits.startswith("7"):      # 701 111 11 11 -> +7 701 ...
        digits = "7" + digits
    if not 7 <= len(digits) <= 15:
        raise ValueError
    return "+" + digits


def resolve_login(identifier):
    """Username or email -> the real username (any letter case). Unknown -> returned as typed."""
    from .models import User
    identifier = (identifier or "").strip()
    if not identifier:
        return ""
    field = "email__iexact" if "@" in identifier else "username__iexact"
    user = User.objects.filter(**{field: identifier}).only("username").first()
    return user.username if user else identifier


def display_name(user):
    """'Aigerim K.' for reviews; the username if no name is given."""
    first = (user.first_name or "").strip()
    last = (user.last_name or "").strip()
    if first:
        return f"{first} {last[0]}." if last else first
    return user.username
