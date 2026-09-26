from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "עלמה – ניהול המלצות"
admin.site.site_url = settings.SITE_ORIGIN

urlpatterns = [
    # Admin login goes through the throttled owner login page.
    path("admin/login/", RedirectView.as_view(url="/reviews/manage/login/", query_string=True)),
    path("admin/", admin.site.urls),
    path("", include("reviews.urls")),
]
