from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import (
    Application,
    Job,
    JobCategory,
    Notification,
    Review,
    SubmissionFile,
    User,
    WorkSubmission,
)


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    fieldsets = DjangoUserAdmin.fieldsets + (
        (
            "Marketplace Profile",
            {
                "fields": (
                    "role",
                    "phone",
                    "location_city",
                    "rating_avg",
                    "rating_count",
                    "created_at",
                    "updated_at",
                )
            },
        ),
    )
    readonly_fields = ("rating_avg", "rating_count", "created_at", "updated_at")
    list_display = ("username", "email", "role", "is_staff", "rating_avg", "rating_count")
    list_filter = ("role", "is_active", "is_staff")
    search_fields = ("username", "email", "first_name", "last_name")


@admin.register(JobCategory)
class JobCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "created_at", "updated_at")
    search_fields = ("name",)
    prepopulated_fields = {"slug": ("name",)}


class ApplicationInline(admin.TabularInline):
    model = Application
    extra = 0
    readonly_fields = ("freelancer", "proposed_budget", "proposed_days", "status", "created_at")
    can_delete = False


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("title", "employer", "display_categories", "status", "deadline_date", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title", "description", "location_city")
    autocomplete_fields = ("employer", "category", "selected_application")
    
    inlines = [ApplicationInline]
    readonly_fields = ("created_at", "updated_at")

    # 3. สร้างฟังก์ชันเพื่อแสดงผลโดยอ้างอิงจาก 'obj.category.all()'
    @admin.display(description='Categories')
    def display_categories(self, obj):
        """แสดง Categories ทั้งหมดเป็นข้อความ"""
        return ", ".join([cat.name for cat in obj.category.all()])

@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = (
        "job",
        "freelancer",
        "status",
        "proposed_budget",
        "proposed_days",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("job__title", "freelancer__username", "freelancer__email")
    autocomplete_fields = ("job", "freelancer")
    readonly_fields = ("created_at", "updated_at")


@admin.register(WorkSubmission)
class WorkSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "job", "application", "submitted_by", "status", "created_at")
    list_filter = ("status",)
    search_fields = ("job__title", "submitted_by__username")
    autocomplete_fields = ("job", "application", "submitted_by")
    readonly_fields = ("created_at", "updated_at")


@admin.register(SubmissionFile)
class SubmissionFileAdmin(admin.ModelAdmin):
    list_display = ("submission", "original_name", "mime_type", "size_bytes", "created_at")
    search_fields = ("original_name", "submission__job__title")
    autocomplete_fields = ("submission",)
    readonly_fields = ("created_at",)


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ("job", "reviewer", "reviewee", "rating", "created_at")
    list_filter = ("rating",)
    search_fields = ("job__title", "reviewer__username", "reviewee__username")
    autocomplete_fields = ("job", "reviewer", "reviewee")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("user", "type", "title", "is_read", "created_at")
    list_filter = ("type", "is_read")
    search_fields = ("title", "message", "user__username", "user__email")
    autocomplete_fields = ("user",)
    readonly_fields = ("created_at",)
