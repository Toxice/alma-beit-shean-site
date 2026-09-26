from django.contrib import admin

from reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author_name", "short_text", "stay_month", "stay_year", "created_at", "is_approved")
    list_editable = ("is_approved",)
    list_filter = ("is_approved",)
    search_fields = ("author_name", "text")
    readonly_fields = ("user", "created_at")

    @admin.display(description="המלצה")
    def short_text(self, obj):
        return obj.text[:60] + ("…" if len(obj.text) > 60 else "")
