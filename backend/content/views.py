from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.views.static import serve

from content.models import FaqItem, GalleryTab


@require_GET
def content_api(request):
    gallery = []
    for tab in GalleryTab.objects.prefetch_related("photos"):
        photos = [
            {
                "url": request.build_absolute_uri(photo.image.url),
                "alt": photo.alt_text,
                "width": photo.width,
                "height": photo.height,
            }
            for photo in tab.photos.all()
        ]
        if photos:  # never show an empty tab on the site
            gallery.append({"title": tab.title, "photos": photos})
    faq = [{"q": item.question, "a": item.answer} for item in FaqItem.objects.all()]
    response = JsonResponse({"gallery": gallery, "faq": faq})
    response["Access-Control-Allow-Origin"] = settings.SITE_ORIGIN
    return response


@require_GET
def media(request, path):
    # ponytail: Django serves the photos itself; fine for ~60 images on a small site.
    # If traffic grows, move them to a bucket or let Cloudflare cache /media/.
    response = serve(request, path, document_root=settings.MEDIA_ROOT)
    response["Cache-Control"] = "public, max-age=31536000, immutable"  # safe: every upload has a unique name
    return response
