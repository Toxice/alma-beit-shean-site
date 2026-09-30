import json
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction

from content.models import FaqItem, GalleryPhoto, GalleryTab

SEED_DIR = Path(__file__).resolve().parents[2] / "seed"


class Command(BaseCommand):
    help = "Load the site's original gallery and FAQ. Does nothing if any content already exists."

    def handle(self, *args, **options):
        if GalleryTab.objects.exists() or GalleryPhoto.objects.exists() or FaqItem.objects.exists():
            self.stdout.write("content already seeded, skipping")
            return
        data = json.loads((SEED_DIR / "content.json").read_text(encoding="utf-8"))
        with transaction.atomic():
            for tab_order, tab_data in enumerate(data["gallery"], start=1):
                tab = GalleryTab.objects.create(title=tab_data["title"], order=tab_order)
                for photo_order, photo in enumerate(tab_data["photos"], start=1):
                    with open(SEED_DIR / photo["file"], "rb") as fh:
                        GalleryPhoto(
                            tab=tab, alt_text=photo["alt"], order=photo_order, image=File(fh, name=photo["file"])
                        ).save()
            for order, item in enumerate(data["faq"], start=1):
                FaqItem.objects.create(question=item["q"], answer=item["a"], order=order)
        self.stdout.write(
            f"seeded {GalleryTab.objects.count()} tabs, {GalleryPhoto.objects.count()} photos, "
            f"{FaqItem.objects.count()} FAQ items"
        )
