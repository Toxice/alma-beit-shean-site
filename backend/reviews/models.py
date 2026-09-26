from datetime import date

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import models

FIRST_YEAR = 2020


class Review(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="reviews"
    )
    # Snapshot of the Google profile at submit time.
    author_name = models.CharField("שם", max_length=100)
    avatar_url = models.URLField("תמונה", max_length=500, blank=True)
    # TextField max_length is not enforced by model validation, hence the validator.
    text = models.TextField(
        "המלצה",
        max_length=1000,
        validators=[MinLengthValidator(10), MaxLengthValidator(1000)],
    )
    stay_month = models.PositiveSmallIntegerField(
        "חודש שהות", validators=[MinValueValidator(1), MaxValueValidator(12)]
    )
    stay_year = models.PositiveSmallIntegerField(
        "שנת שהות", validators=[MinValueValidator(FIRST_YEAR)]
    )
    is_approved = models.BooleanField("מאושר לפרסום", default=False)
    created_at = models.DateTimeField("נשלח", auto_now_add=True)

    class Meta:
        ordering = ["-stay_year", "-stay_month", "-created_at"]
        verbose_name = "המלצה"
        verbose_name_plural = "המלצות"

    def clean(self):
        today = date.today()
        if self.stay_year and self.stay_month:
            if (self.stay_year, self.stay_month) > (today.year, today.month):
                raise ValidationError("תאריך השהות לא יכול להיות בעתיד.")

    def __str__(self):
        return f"{self.author_name} ({self.stay_month}/{self.stay_year})"
