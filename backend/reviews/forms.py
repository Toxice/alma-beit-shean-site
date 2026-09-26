from datetime import date

from django import forms

from reviews.models import FIRST_YEAR, Review

HEBREW_MONTHS = [
    "ינואר", "פברואר", "מרץ", "אפריל", "מאי", "יוני",
    "יולי", "אוגוסט", "ספטמבר", "אוקטובר", "נובמבר", "דצמבר",
]


class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ["text", "stay_month", "stay_year"]
        widgets = {
            "text": forms.Textarea(attrs={"rows": 6, "maxlength": 1000, "minlength": 10}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["stay_month"].widget = forms.Select(
            choices=[(i, name) for i, name in enumerate(HEBREW_MONTHS, start=1)]
        )
        years = range(date.today().year, FIRST_YEAR - 1, -1)
        self.fields["stay_year"].widget = forms.Select(choices=[(y, y) for y in years])
