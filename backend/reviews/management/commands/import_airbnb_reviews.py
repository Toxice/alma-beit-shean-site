import json
import os
from datetime import datetime
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from reviews.models import Review

ACTOR = "tri_angle~airbnb-reviews-scraper"
DEFAULT_LISTING_URL = "https://www.airbnb.com/rooms/1771157482793114563"
TIMEOUT_SECONDS = 300  # Apify's cap for run-sync endpoints
MAX_TEXT = 1000
MAX_NAME = 100
FALLBACK_NAME = "אורח/ת"


def fetch_reviews(token, listing_url):
    """Run the Apify actor and return its dataset items. Raises CommandError on any failure."""
    request = Request(
        f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items",
        data=json.dumps({"startUrls": [{"url": listing_url}]}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            items = json.loads(response.read())
    except (URLError, TimeoutError, ValueError) as exc:  # ValueError covers bad JSON
        raise CommandError(f"Apify request failed: {exc}") from exc
    if not isinstance(items, list):
        raise CommandError(f"Apify returned {type(items).__name__}, expected a list")
    return items


def to_fields(item):
    """Map one Apify item to Review fields, or None if it can't be shown."""
    if not isinstance(item, dict):
        return None
    review_id = item.get("id")
    text = (item.get("text") or "").strip()
    if review_id in (None, "") or not text:
        return None
    try:
        created = datetime.fromisoformat(item["createdAt"])
    except (KeyError, TypeError, ValueError):
        return None
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1] + "…"
    reviewer = item.get("reviewer") if isinstance(item.get("reviewer"), dict) else {}
    name = (reviewer.get("firstName") or "").strip() or FALLBACK_NAME
    return {
        "author_name": name[:MAX_NAME],
        "text": text,
        # Airbnb hides the stay date; reviews come within 14 days of checkout, so the month is close enough.
        "stay_month": created.month,
        "stay_year": created.year,
        "source": Review.Source.AIRBNB,
        "external_id": str(review_id),
        "is_approved": True,
    }


class Command(BaseCommand):
    help = "Import new Airbnb reviews of the Alma listing through Apify."

    def handle(self, *args, **options):
        token = os.environ.get("APIFY_TOKEN")
        if not token:
            raise CommandError("APIFY_TOKEN is not set")
        listing_url = os.environ.get("AIRBNB_LISTING_URL") or DEFAULT_LISTING_URL

        items = fetch_reviews(token, listing_url)
        known = set(Review.objects.exclude(external_id=None).values_list("external_id", flat=True))
        created = skipped = 0
        with transaction.atomic():
            for index, item in enumerate(items):
                fields = to_fields(item)
                if fields is None:
                    self.stderr.write(f"skipped unusable item #{index}")
                    skipped += 1
                elif fields["external_id"] in known:
                    skipped += 1
                else:
                    Review.objects.create(**fields)
                    known.add(fields["external_id"])
                    created += 1
        self.stdout.write(f"fetched {len(items)}, created {created}, skipped {skipped}")
