from datetime import date

from django import forms

from reviews.models import FIRST_YEAR, HEBREW_MONTHS, Review


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["author_name", "text", "stay_month", "stay_year"]
        widgets = {
            "author_name": forms.TextInput(attrs={"autocomplete": "name"}),
            "text": forms.Textarea(attrs={"rows": 6, "maxlength": 1000, "minlength": 10}),
        }

    # Honeypot: hidden from people, bots fill every field. See write_review.
    website = forms.CharField(required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stay_month"].widget = forms.Select(
            choices=[(i, name) for i, name in enumerate(HEBREW_MONTHS, start=1)]
        )
        years = range(date.today().year, FIRST_YEAR - 1, -1)
        self.fields["stay_year"].widget = forms.Select(choices=[(y, y) for y in years])
