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
