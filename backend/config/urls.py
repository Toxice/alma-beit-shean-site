from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "עלמה – פאנל ניהול"
admin.site.site_url = settings.SITE_ORIGIN

urlpatterns = [
    # Admin lives at an unlisted path (not linked from the site); login goes through the throttled owner page.
    path("alma-manage-x7/login/", RedirectView.as_view(url="/reviews/manage/login/", query_string=True)),
    path("alma-manage-x7/", admin.site.urls),
    path("", include("reviews.urls")),
]
