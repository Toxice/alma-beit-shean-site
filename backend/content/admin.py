from adminsortable2.admin import SortableAdminMixin, SortableTabularInline
from django.contrib import admin
from django.utils.html import format_html

from content.models import FaqItem, GalleryPhoto, GalleryTab


class GalleryPhotoInline(SortableTabularInline):
    model = GalleryPhoto
    extra = 1
    readonly_fields = ("preview",)

    @admin.display(description="תצוגה מקדימה")
    def preview(self, obj):
        if not obj.pk or not obj.image:
            return ""
        return format_html('<img src="{}" alt="" style="height:64px;border-radius:6px;">', obj.image.url)


@admin.register(GalleryTab)
class GalleryTabAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ("title", "photo_count")
    inlines = [GalleryPhotoInline]

    @admin.display(description="מספר תמונות")
    def photo_count(self, obj):
        return obj.photos.count()


@admin.register(FaqItem)
class FaqItemAdmin(SortableAdminMixin, admin.ModelAdmin):
    list_display = ("question",)
