"""Permission-protected inbox for customer complaints and in-app responses."""
from django import forms
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods, require_safe

from .models import Complaint


STATUS_CHOICES = (
    ("new", "Новое"),
    ("in_progress", "В работе"),
    ("resolved", "Решено"),
)


def _require_view(user):
    if not (user.has_perm("shop.view_complaint") or user.has_perm("shop.change_complaint")):
        raise PermissionDenied


class ComplaintResponseForm(forms.Form):
    status = forms.ChoiceField(label="Статус обращения", choices=STATUS_CHOICES)
    staff_response = forms.CharField(
        label="Ответ покупателю", required=False, max_length=5000,
        widget=forms.Textarea(attrs={"rows": 7, "maxlength": 5000}),
        help_text="Ответ будет виден покупателю в книге жалоб. Чтобы закрыть обращение, напишите ответ.",
    )

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("status") == "resolved" and not cleaned.get("staff_response"):
            self.add_error("staff_response", "Напишите ответ покупателю перед закрытием обращения.")
        return cleaned


@require_safe
def complaints(request):
    _require_view(request.user)
    q = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "")
    queryset = Complaint.objects.select_related("user", "order").order_by("-created_at", "-pk")
    if q:
        queryset = queryset.filter(
            Q(subject__icontains=q) | Q(message__icontains=q) | Q(user__username__icontains=q)
        )
    if status_filter in dict(STATUS_CHOICES):
        queryset = queryset.filter(status=status_filter)
    else:
        status_filter = ""
    return render(request, "shop/staff_complaints.html", {
        "page_obj": Paginator(queryset, 20).get_page(request.GET.get("page")),
        "q": q, "status_filter": status_filter, "status_choices": STATUS_CHOICES,
        "active_section": "complaints",
    })


@require_http_methods(["GET", "HEAD", "POST"])
def complaint_detail(request, pk):
    _require_view(request.user)
    can_respond = request.user.has_perm("shop.change_complaint")
    if request.method == "POST" and not can_respond:
        raise PermissionDenied
    with transaction.atomic():
        queryset = Complaint.objects.select_related("user", "order", "responded_by")
        if request.method == "POST":
            queryset = queryset.select_for_update(of=("self",))
        complaint = get_object_or_404(queryset, pk=pk)
        form = ComplaintResponseForm(
            request.POST if request.method == "POST" else None,
            initial={"status": complaint.status, "staff_response": complaint.staff_response},
        )
        if request.method == "POST" and form.is_valid():
            response = form.cleaned_data["staff_response"]
            if response != complaint.staff_response:
                complaint.staff_response = response
                complaint.responded_by = request.user if response else None
                complaint.replied_at = timezone.now() if response else None
            complaint.status = form.cleaned_data["status"]
            complaint.save(update_fields=[
                "status", "staff_response", "responded_by", "replied_at", "updated_at",
            ])
            messages.success(request, "Обращение обновлено. Ответ доступен покупателю в книге жалоб.")
            return redirect("staff_complaint_detail", pk=complaint.pk)
    return render(request, "shop/staff_complaint_detail.html", {
        "complaint": complaint, "form": form, "can_respond": can_respond,
        "active_section": "complaints",
    })
