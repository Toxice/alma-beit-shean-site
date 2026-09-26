from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "עלמה – ניהול המלצות"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("allauth.urls")),
    path("", include("reviews.urls")),
]
