"""
URL configuration for Project project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
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
from django.urls import path

from login import views as login_views
from register import views as register_views
from customer import views as customer_views
from rider import views as rider_views
from merchant import views as merchant_views
from platforme import views as platform_views
from home import views as home_views

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", home_views.HomeView.as_view(), name="home"),
    path("info/terms/", home_views.terms, name="terms"),
    path("info/privacy/", home_views.privacy, name="privacy"),
    path("info/security/", home_views.security, name="security"),
    path("info/contact/", home_views.contact, name="contact"),
    path("login/", login_views.login, name="login"),
    path("forgot-password/", login_views.forgot_password, name="forgot_password"),
    path("register/", register_views.register, name="register"),
    path("register/check-username/", register_views.check_username, name="check_username"),
    path("customer/", customer_views.customer, name="customer"),
    path("customer/get-merchant-detail/<int:merchant_id>/<int:platform_id>/", customer_views.get_merchant_detail, name="get_merchant_detail"),
    path("customer/place-order/", customer_views.place_order, name="place_order"),
    path("customer/get-orders/", customer_views.get_orders, name="get_orders"),
    path("customer/search-merchants/", customer_views.search_merchants, name="search_merchants"),
    path("customer/delete-order/<int:order_id>/", customer_views.delete_order, name="delete_order"),
    path("customer/pickup-order/<int:order_id>/", customer_views.pickup_order, name="pickup_order"),
    path("customer/rate-order/<int:order_id>/", customer_views.rate_order, name="rate_order"),
    path("rider/", rider_views.rider, name="rider"),
    path("rider/apply-platform/", rider_views.apply_platform, name="apply_platform"),
    path("rider/accept-orders/", rider_views.accept_orders, name="accept_orders"),
    path("rider/cancel-orders/", rider_views.cancel_orders, name="cancel_orders"),
    path("rider/complete-orders/", rider_views.complete_orders, name="complete_orders"),
    path("merchant/", merchant_views.merchant, name="merchant"),
    path("merchant/add-meal/", merchant_views.add_meal, name="add_meal"),
    path("merchant/get-meals/", merchant_views.get_meals, name="get_meals"),
    path("merchant/edit-meal/<int:meal_id>/", merchant_views.edit_meal, name="delete_meal"),
    path("merchant/delete-meal/<int:meal_id>/", merchant_views.delete_meal, name="delete_meal"),
    path('merchant/apply-platform/', merchant_views.apply_platform, name='apply_platform'),
    path('merchant/set-discount/', merchant_views.set_discount, name='set_discount'),
    path('merchant/edit-discount/<int:discount_id>/', merchant_views.edit_discount, name='edit_discount'),
    path('merchant/delete-discount/<int:discount_id>/', merchant_views.delete_discount, name='delete_discount'),
    path('merchant/get-discounts/', merchant_views.get_discounts, name='get_discounts'),
    path('merchant/get-orders/', merchant_views.get_orders, name='get_orders'),
    path('merchant/delete-order/<int:order_id>/', merchant_views.delete_order, name='delete_order'),
    path("platform/", platform_views.platform, name="platform"),
    path("platform/approve-merchant-request/", platform_views.approve_merchant_request, name="approve_merchant_request"),
    path("platform/reject-merchant-request/", platform_views.reject_merchant_request, name="reject_merchant_request"),
    path("platform/remove-merchant/", platform_views.remove_merchant, name="remove_merchant"),
    path("platform/approve-rider-request/", platform_views.approve_rider_request, name="approve_rider_request"),
    path("platform/reject-rider-request/", platform_views.reject_rider_request, name="reject_rider_request"),
    path("platform/remove-rider/", platform_views.remove_rider, name="remove_rider"),
    path("platform/delete-order/", platform_views.delete_order, name="delete_order"),
]
