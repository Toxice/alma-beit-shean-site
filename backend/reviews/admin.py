from django.contrib import admin

from reviews.models import Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("author_name", "short_text", "source", "stay_month", "stay_year", "created_at", "is_approved")
    list_editable = ("is_approved",)
    list_filter = ("is_approved", "source")
    search_fields = ("author_name", "text")
    readonly_fields = ("created_at", "source", "external_id")

    def has_delete_permission(self, request, obj=None):
        # A deleted Airbnb import would come back on the next run; hide it instead.
        if obj is not None and obj.source == Review.Source.AIRBNB:
            return False
        return super().has_delete_permission(request, obj)

    @admin.display(description="המלצה")
    def short_text(self, obj):
        return obj.text[:60] + ("…" if len(obj.text) > 60 else "")
