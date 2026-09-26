from django.conf import settings
from django.contrib.auth.decorators import user_passes_test
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from reviews.forms import ReviewForm
from reviews.models import Review


def site_url(request):
    """Template context: link back to the static site and load its images."""
    return {"site_url": settings.SITE_ORIGIN}


@require_GET
def reviews_api(request):
    reviews = [
        {
            "name": r.author_name,
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


def write_review(request):
    # ponytail: honeypot + owner approval only; add per-IP rate limit if spam gets through.
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data["website"]:
            form.save()
        return redirect("reviews:thanks")
    return render(request, "reviews/write.html", {"form": form})


def thanks(request):
    return render(request, "reviews/thanks.html")


staff_required = user_passes_test(lambda u: u.is_active and u.is_staff)


@staff_required
def manage(request):
    reviews = Review.objects.order_by("is_approved", "-created_at")
    return render(request, "reviews/manage.html", {"reviews": reviews})


@require_POST
@staff_required
def manage_action(request, pk):
    review = get_object_or_404(Review, pk=pk)
    action = request.POST.get("action")
    if action == "delete":
        review.delete()
    elif action in ("approve", "hide"):
        review.is_approved = action == "approve"
        review.save(update_fields=["is_approved"])
    return redirect("reviews:manage")
