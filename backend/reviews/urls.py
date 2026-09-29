from django.contrib.auth import views as auth_views
from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("api/reviews/", views.reviews_api, name="api"),
    path("reviews/write/", views.write_review, name="write"),
    path("reviews/thanks/", views.thanks, name="thanks"),
    path("reviews/manage/", views.manage, name="manage"),
    path("reviews/manage/<int:pk>/", views.manage_action, name="manage_action"),
    path("reviews/manage/login/", views.manage_login, name="manage_login"),
    path("reviews/manage/logout/", auth_views.LogoutView.as_view(next_page="reviews:manage_login"), name="manage_logout"),
]
