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

from shop import complaints_staff, reports, staff
from shop.auth_forms import ProtectedAdminAuthenticationForm

admin.site.index_template = "shop/admin_index.html"
admin.site.login_form = ProtectedAdminAuthenticationForm


urlpatterns = [
    path("staff/", admin.site.admin_view(staff.dashboard), name="staff_dashboard"),
    path("staff/catalog/", admin.site.admin_view(staff.catalog), name="staff_catalog"),
    path("staff/catalog/add/", admin.site.admin_view(staff.product_form), name="staff_product_add"),
    path("staff/catalog/<int:pk>/", admin.site.admin_view(staff.product_form), name="staff_product_edit"),
    path("staff/catalog/<int:pk>/delete/", admin.site.admin_view(staff.product_delete), name="staff_product_delete"),
    path("staff/categories/", admin.site.admin_view(staff.categories), name="staff_categories"),
    path("staff/categories/add/", admin.site.admin_view(staff.category_form), name="staff_category_add"),
    path("staff/categories/<int:pk>/", admin.site.admin_view(staff.category_form), name="staff_category_edit"),
    path("staff/categories/<int:pk>/delete/", admin.site.admin_view(staff.category_delete), name="staff_category_delete"),
    path("staff/orders/", admin.site.admin_view(staff.orders), name="staff_orders"),
    path("staff/orders/<int:pk>/", admin.site.admin_view(staff.order_detail), name="staff_order_detail"),
    path("staff/users/", admin.site.admin_view(staff.users), name="staff_users"),
    path("staff/complaints/", admin.site.admin_view(complaints_staff.complaints), name="staff_complaints"),
    path("staff/complaints/<int:pk>/", admin.site.admin_view(complaints_staff.complaint_detail), name="staff_complaint_detail"),
    path("staff/reports/", admin.site.admin_view(reports.reports), name="staff_reports"),
    path("staff/reports/<slug:kind>.csv", admin.site.admin_view(reports.reports_csv), name="staff_reports_csv"),
    path("admin/", admin.site.urls),
    path("api/", include("shop.urls")),
]
