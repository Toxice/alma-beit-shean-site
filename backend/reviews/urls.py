from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("api/reviews/", views.reviews_api, name="api"),
    path("reviews/login/", views.login_page, name="login"),
    path("reviews/write/", views.write_review, name="write"),
    path("reviews/thanks/", views.thanks, name="thanks"),
]
