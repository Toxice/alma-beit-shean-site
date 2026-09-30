from uuid import uuid4

from django.core.validators import MaxLengthValidator
from django.db import models, transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from content.images import to_web_jpeg, validate_upload


class GalleryTab(models.Model):
    title = models.CharField("כותרת הלשונית", max_length=60)
    order = models.PositiveIntegerField("סדר", default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "לשונית גלריה"
        verbose_name_plural = "לשוניות גלריה"

    def __str__(self):
        return self.title


class GalleryPhoto(models.Model):
    tab = models.ForeignKey(GalleryTab, on_delete=models.CASCADE, related_name="photos", verbose_name="לשונית")
    image = models.ImageField("תמונה", upload_to="gallery/", validators=[validate_upload])
    alt_text = models.CharField("תיאור התמונה (לנגישות)", max_length=150)
    width = models.PositiveIntegerField(default=0, editable=False)
    height = models.PositiveIntegerField(default=0, editable=False)
    order = models.PositiveIntegerField("סדר", default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "תמונה"
        verbose_name_plural = "תמונות"

    def __str__(self):
        return self.alt_text

    def save(self, *args, **kwargs):
        old_name = None
        if self.pk:
            old_name = GalleryPhoto.objects.filter(pk=self.pk).values_list("image", flat=True).first()
        if self.image and not self.image._committed:  # a new upload, not an alt-text-only edit
            content, self.width, self.height = to_web_jpeg(self.image)
            # Unique name per upload: a replaced photo gets a new URL, so no cache shows the old one.
            self.image.save(f"{uuid4().hex}.jpg", content, save=False)
        super().save(*args, **kwargs)
        if old_name and old_name != self.image.name:
            storage = self.image.storage
            # After commit only: a rolled-back save must not lose the photo the row still points to.
            transaction.on_commit(lambda: storage.delete(old_name))


@receiver(post_delete, sender=GalleryPhoto)
def delete_photo_file(sender, instance, **kwargs):
    # Also fires for each photo when its tab is deleted (cascade).
    if instance.image:
        storage, name = instance.image.storage, instance.image.name
        transaction.on_commit(lambda: storage.delete(name))


class FaqItem(models.Model):
    question = models.CharField("שאלה", max_length=200)
    answer = models.TextField("תשובה", max_length=1000, validators=[MaxLengthValidator(1000)])
    order = models.PositiveIntegerField("סדר", default=0, db_index=True)

    class Meta:
        ordering = ["order"]
        verbose_name = "שאלה נפוצה"
        verbose_name_plural = "שאלות נפוצות"

    def __str__(self):
        return self.question
