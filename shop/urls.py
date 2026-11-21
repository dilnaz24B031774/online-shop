from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from . import api, auth_views, complaints_api, password_reset, telegram_recovery

urlpatterns = [
    # catalogue (open for everyone)
    path("categories/", api.categories),
    path("products/", api.products),
    path("products/filters/", api.product_filters),
    path("products/best-sellers/", api.best_sellers),
    path("products/<int:pk>/notify-me/", api.notify_me),
    path("top/", api.top),
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
    path("auth/telegram/password-reset/", telegram_recovery.request_reset),
    path("auth/telegram/password-reset/confirm/", telegram_recovery.confirm_reset),
    path("auth/refresh/", TokenRefreshView.as_view()),      # {refresh} -> new access token
    path("me/", api.me),
    path("cities/", api.cities),
    path("me/password/", api.change_password),
    path("me/telegram/", telegram_recovery.status),
    path("me/telegram/link/", telegram_recovery.start_link),
    path("me/telegram/unlink/", telegram_recovery.unlink),
    path("addresses/", api.addresses),

    # private customer complaints and staff responses
    path("complaints/", complaints_api.complaints),
    path("complaints/<int:pk>/", complaints_api.complaint_detail),

    # cart and orders (login required)
    path("cart/", api.cart),
    path("checkout/", api.checkout),
    path("orders/", api.my_orders),
    path("orders/<int:pk>/cancel/", api.cancel_order),
    path("favorites/", api.favorites),
    path("favorites/<int:product_id>/", api.remove_favorite),
    path("orders/<int:pk>/pay-qr/", api.pay_qr),
    path("network/", api.network),
    path("qr/<str:token>/", api.qr_info),
    path("qr/<str:token>/pay/", api.qr_pay),
    path("promo/check/", api.promo_check),
    path("cards/", api.saved_cards),
    path("cards/<int:pk>/", api.delete_card),
    path("stock-alerts/", api.stock_alerts),

    # notifications (login required)
    path("notifications/", api.notifications),
    path("notifications/read-all/", api.notifications_read_all),
    path("notifications/<int:pk>/read/", api.notification_read),
]
