"""Authenticated customer access to their private complaints book."""
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from .models import Complaint, Order


class ComplaintSerializer(serializers.ModelSerializer):
    # Scope the relation itself, so another customer's order cannot be attached.
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.none(), allow_null=True, required=False,
        pk_field=serializers.IntegerField(min_value=1, max_value=9223372036854775807),
    )
    subject = serializers.CharField(max_length=150, trim_whitespace=True)
    message = serializers.CharField(min_length=10, max_length=5000, trim_whitespace=True)

    class Meta:
        model = Complaint
        fields = [
            "id", "order", "category", "subject", "message", "status",
            "staff_response", "replied_at", "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "status", "staff_response", "replied_at", "created_at", "updated_at",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        if request is not None and request.user.is_authenticated:
            self.fields["order"].queryset = Order.objects.filter(user=request.user)


def _mine(user):
    return Complaint.objects.filter(user=user).select_related("user", "order")


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def complaints(request):
    if request.method == "POST":
        serializer = ComplaintSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user)
        return Response(serializer.data, status=201)
    return Response(ComplaintSerializer(_mine(request.user), many=True).data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def complaint_detail(request, pk):
    complaint = get_object_or_404(_mine(request.user), pk=pk)
    return Response(ComplaintSerializer(complaint).data)
