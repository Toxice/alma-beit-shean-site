from django.urls import path, re_path

from content import views

app_name = "content"

urlpatterns = [
    path("api/content/", views.content_api, name="api"),
    re_path(r"^media/(?P<path>.+)$", views.media, name="media"),
]
