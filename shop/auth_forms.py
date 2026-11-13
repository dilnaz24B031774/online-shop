"""The admin session login uses the same counters as JWT sign-in."""
from django import forms
from django.contrib.admin.forms import AdminAuthenticationForm
from django.http import HttpRequest
from django.utils.functional import cached_property

from .login_security import (
    SecurityRateLimited, get_login_state, issue_challenge, login_attempt,
    record_login_failure, record_login_success, verify_challenge,
)


class ProtectedAdminAuthenticationForm(AdminAuthenticationForm):
    password = forms.CharField(
        label="Пароль", strip=False, max_length=4096,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )
    challenge_id = forms.CharField(required=False, widget=forms.HiddenInput)
    challenge_answer = forms.CharField(
        required=False, max_length=3, label="Ответ на проверку",
        widget=forms.TextInput(attrs={"inputmode": "numeric", "autocomplete": "off"}),
    )
    website = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, request=None, *args, **kwargs):
        request = request or HttpRequest()
        super().__init__(request, *args, **kwargs)
        username = self.data.get("username", "") if self.is_bound else ""
        self.security_state = get_login_state(request, username)
        self.challenge_error = ""

    @property
    def retry_after(self):
        return self.security_state["retry_after"]

    @property
    def challenge_required(self):
        return self.security_state["challenge_required"]

    @cached_property
    def bot_challenge(self):
        if not self.challenge_required or self.retry_after:
            return None
        try:
            return issue_challenge(self.request)
        except SecurityRateLimited as error:
            self.challenge_error = error.detail
            return None

    def _failure_message(self, state, *, challenge=False):
        self.security_state = state
        if state["retry_after"]:
            return forms.ValidationError(
                "Вход временно заблокирован. Повторите через %(seconds)s сек.",
                code="login_locked", params={"seconds": state["retry_after"]},
            )
        return forms.ValidationError(
            ("Проверка не пройдена. Решите новый пример и повторите вход." if challenge
             else "Неверный логин или пароль сотрудника. Осталось попыток: %(remaining)s."),
            code="challenge_required" if challenge else "invalid_login",
            params={"remaining": state["remaining_attempts"]},
        )

    def clean(self):
        username = self.data.get("username", "")
        failure = None
        cleaned = self.cleaned_data
        # A ValidationError must be raised after leaving the transaction so that
        # failed-attempt counters and consumed challenge nonces are committed.
        with login_attempt(self.request, username):
            state = get_login_state(self.request, username)
            if state["retry_after"]:
                failure = self._failure_message(state)
            elif self.data.get("website"):
                failure = self._failure_message(record_login_failure(self.request, username))
            elif state["challenge_required"] and not verify_challenge(
                self.request, self.data.get("challenge_id"), self.data.get("challenge_answer"),
            ):
                failure = self._failure_message(record_login_failure(self.request, username), challenge=True)
            elif not self.cleaned_data.get("username") or not self.cleaned_data.get("password"):
                failure = self._failure_message(record_login_failure(self.request, username))
            else:
                try:
                    cleaned = super().clean()
                except forms.ValidationError:
                    failure = self._failure_message(record_login_failure(self.request, username))
                else:
                    record_login_success(self.request, username)
                    self.security_state = get_login_state(self.request, username)
        if failure:
            raise failure
        return cleaned
