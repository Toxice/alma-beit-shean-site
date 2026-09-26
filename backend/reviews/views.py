from datetime import timedelta

from django.conf import settings
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import user_passes_test
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from reviews.forms import ReviewForm
from reviews.models import Review

# Abuse limits. Global on purpose: client IPs behind Railway/Cloudflare are spoofable, a global count is not.
REVIEWS_PER_HOUR = 20
LOGIN_FAILURES_LIMIT = 20
LOGIN_LOCK_SECONDS = 15 * 60
LOGIN_FAILURES_KEY = "manage-login-failures"


def busy(request):
    return render(request, "reviews/busy.html", status=429)


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
    # Browser re-checks on every load, so an approved review shows at once. Payload is tiny.
    response["Cache-Control"] = "no-cache"
    return response


def write_review(request):
    if request.method == "POST":
        recent = Review.objects.filter(created_at__gte=timezone.now() - timedelta(hours=1)).count()
        if recent >= REVIEWS_PER_HOUR:
            return busy(request)
    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        if not form.cleaned_data["website"]:
            form.save()
        return redirect("reviews:thanks")
    return render(request, "reviews/write.html", {"form": form})


def thanks(request):
    return render(request, "reviews/thanks.html")


def _is_staff(user):
    # Logged-in non-staff get 403; redirecting them to login would loop (redirect_authenticated_user).
    if user.is_authenticated and not user.is_staff:
        raise PermissionDenied
    return user.is_active and user.is_staff


staff_required = user_passes_test(_is_staff)

_login = auth_views.LoginView.as_view(template_name="reviews/manage_login.html", redirect_authenticated_user=True)


def manage_login(request):
    # ponytail: counter lives in the local-memory cache, so each gunicorn worker counts alone
    # (2 workers = 40 tries per 15 min). Move CACHES to Redis if more workers are added.
    if request.method == "POST" and cache.get(LOGIN_FAILURES_KEY, 0) >= LOGIN_FAILURES_LIMIT:
        return busy(request)
    response = _login(request)
    if request.method == "POST" and response.status_code == 200:  # form re-rendered = wrong password
        cache.add(LOGIN_FAILURES_KEY, 0, LOGIN_LOCK_SECONDS)
        cache.incr(LOGIN_FAILURES_KEY)
    return response


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
