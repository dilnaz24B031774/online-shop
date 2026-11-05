"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import include, path

from shop import staff

admin.site.index_template = "shop/admin_index.html"


urlpatterns = [
    path("staff/catalog/", admin.site.admin_view(staff.catalog), name="staff_catalog"),
    path("staff/catalog/add/", admin.site.admin_view(staff.product_form), name="staff_product_add"),
    path("staff/catalog/<int:pk>/", admin.site.admin_view(staff.product_form), name="staff_product_edit"),
    path("admin/", admin.site.urls),
    path("api/", include("shop.urls")),
]
