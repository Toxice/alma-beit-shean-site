from django.urls import path

from reviews import views

app_name = "reviews"

urlpatterns = [
    path("api/reviews/", views.reviews_api, name="api"),
]
