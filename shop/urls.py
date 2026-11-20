from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import api, auth_views, complaints_api, password_reset

urlpatterns = [
    # catalogue (open for everyone)
    path("categories/", api.categories),
    path("products/", api.products),
    path("products/filters/", api.product_filters),
    path("products/best-sellers/", api.best_sellers),
    path("products/<int:pk>/", api.product_detail),
    path("products/<int:pk>/reviews/", api.add_review),
    path("search/", api.search),
    path("assistant/", api.assistant),

    # accounts and JWT tokens
    path("auth/register/", api.register),
    path("auth/login/", auth_views.login),
    path("auth/challenge/", auth_views.challenge),
    path("auth/password-reset/", password_reset.request_reset),
    path("auth/password-reset/confirm/", password_reset.confirm_reset),
    path("auth/refresh/", TokenRefreshView.as_view()),      # {refresh} -> new access token
    path("me/", api.me),
    path("me/password/", api.change_password),
    path("addresses/", api.addresses),

    # private customer complaints and staff responses
    path("complaints/", complaints_api.complaints),
    path("complaints/<int:pk>/", complaints_api.complaint_detail),

    # cart and orders (login required)
    path("cart/", api.cart),
    path("checkout/", api.checkout),
    path("orders/", api.my_orders),
    path("orders/<int:pk>/cancel/", api.cancel_order),
    path("orders/<int:pk>/pay-qr/", api.pay_qr),
    path("promo/check/", api.promo_check),

    # notifications (login required)
    path("notifications/", api.notifications),
    path("notifications/read-all/", api.notifications_read_all),
    path("notifications/<int:pk>/read/", api.notification_read),
]
