from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import api

urlpatterns = [
    # catalogue (open for everyone)
    path("categories/", api.categories),
    path("products/", api.products),
    path("products/best-sellers/", api.best_sellers),
    path("products/<int:pk>/", api.product_detail),
    path("products/<int:pk>/reviews/", api.add_review),
    path("search/", api.search),
    path("assistant/", api.assistant),

    # accounts and JWT tokens
    path("auth/register/", api.register),
    path("auth/login/", TokenObtainPairView.as_view()),     # {username, password} -> tokens
    path("auth/refresh/", TokenRefreshView.as_view()),      # {refresh} -> new access token
    path("me/", api.me),
    path("addresses/", api.addresses),

    # cart and orders (login required)
    path("cart/", api.cart),
    path("checkout/", api.checkout),
    path("orders/", api.my_orders),
    path("orders/<int:pk>/cancel/", api.cancel_order),
]
