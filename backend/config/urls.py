from django.conf import settings
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "עלמה – ניהול המלצות"
admin.site.site_url = settings.SITE_ORIGIN

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("reviews.urls")),
]
