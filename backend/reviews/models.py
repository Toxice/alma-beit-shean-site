from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import (
    MaxLengthValidator,
    MaxValueValidator,
    MinLengthValidator,
    MinValueValidator,
)
from django.db import models

FIRST_YEAR = 2020
HEBREW_MONTHS = [
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]


class Review(models.Model):
    class Source(models.TextChoices):
        SITE = "site", "אתר"
        AIRBNB = "airbnb", "Airbnb"

    author_name = models.CharField("שם", max_length=100)
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
    source = models.CharField("מקור", max_length=10, choices=Source.choices, default=Source.SITE)
    # Airbnb review ID. NULL for site reviews; the unique index ignores NULLs.
    external_id = models.CharField("מזהה חיצוני", max_length=64, null=True, blank=True, unique=True)

    class Meta:
        ordering = ["-stay_year", "-stay_month", "-created_at"]
        verbose_name = "המלצה"
        verbose_name_plural = "המלצות"

    def clean(self):
        today = date.today()
        if self.stay_year and self.stay_month:
            if (self.stay_year, self.stay_month) > (today.year, today.month):
                raise ValidationError("תאריך השהות לא יכול להיות בעתיד.")

    @property
    def stay_label(self):
        return f"{HEBREW_MONTHS[self.stay_month - 1]} {self.stay_year}"

    def __str__(self):
        return f"{self.author_name} ({self.stay_month}/{self.stay_year})"
