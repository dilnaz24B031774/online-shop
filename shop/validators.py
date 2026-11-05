"""
Password strength rules (task from the instructor).
Django runs them in validate_password() BEFORE the password is hashed:
the database never sees the real password, so the check must happen here.
"""
import re

from django.core.exceptions import ValidationError


class ContainsDigitValidator:
    """The password must contain at least one number."""

    def validate(self, password, user=None):
        if not re.search(r"\d", password):
            raise ValidationError(
                "The password must contain at least one number.",
                code="password_no_digit",
            )

    def get_help_text(self):
        return "Your password must contain at least one number."


class ContainsUppercaseValidator:
    """The password must contain at least one capital letter (A-Z, А-Я)."""

    def validate(self, password, user=None):
        if not any(ch.isupper() for ch in password):
            raise ValidationError(
                "The password must contain at least one capital letter.",
                code="password_no_upper",
            )

    def get_help_text(self):
        return "Your password must contain at least one capital letter."
