from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from reviews.models import Review


@require_GET
def reviews_api(request):
    reviews = [
        {
            "name": r.author_name,
            "avatar": r.avatar_url,
            "text": r.text,
            "stay_month": r.stay_month,
            "stay_year": r.stay_year,
        }
        for r in Review.objects.filter(is_approved=True)
    ]
    response = JsonResponse({"reviews": reviews})
    response["Access-Control-Allow-Origin"] = settings.SITE_ORIGIN
    response["Cache-Control"] = "public, max-age=300"
    return response


from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from reviews.forms import ReviewForm


def google_identity(user):
    """Name + photo from the user's Google account, never the email."""
    account = user.socialaccount_set.filter(provider="google").first()
    data = account.extra_data if account else {}
    name = data.get("name") or user.get_full_name() or "אורח/ת"
    return name[:100], data.get("picture", "")


def login_page(request):
    if request.user.is_authenticated:
        return redirect("reviews:write")
    next_url = request.GET.get("next", "/reviews/write/")
    return render(request, "reviews/login.html", {"next": next_url, "site_url": settings.SITE_ORIGIN})


@login_required
def write_review(request):
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        review = form.save(commit=False)
        review.user = request.user
        review.author_name, review.avatar_url = google_identity(request.user)
        review.save()
        return redirect("reviews:thanks")
    name, avatar = google_identity(request.user)
    return render(
        request,
        "reviews/write.html",
        {"form": form, "name": name, "avatar": avatar, "site_url": settings.SITE_ORIGIN},
    )


def thanks(request):
    return render(request, "reviews/thanks.html", {"site_url": settings.SITE_ORIGIN})
