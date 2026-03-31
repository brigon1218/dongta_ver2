from django.contrib import admin
from .models import Company, JobNotice, JobSeeker


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ['id', 'company_name', 'member', 'phone', 'has_notice', 'created_at']
    search_fields = ['company_name', 'member__username', 'phone']
    list_filter = ['has_notice', 'created_at']
    list_per_page = 20


@admin.register(JobNotice)
class JobNoticeAdmin(admin.ModelAdmin):
    list_display = ['id', 'title', 'company', 'member', 'employment_type', 'is_approved', 'is_premium', 'created_at']
    search_fields = ['title', 'company__company_name', 'member__username']
    list_filter = ['is_approved', 'is_premium', 'employment_type', 'created_at']
    list_per_page = 20
    actions = ['approve_notices']

    def approve_notices(self, request, queryset):
        queryset.update(is_approved=True)
    approve_notices.short_description = "선택된 공고 승인"


@admin.register(JobSeeker)
class JobSeekerAdmin(admin.ModelAdmin):
    list_display = ['id', 'name', 'member', 'phone', 'resume_registered', 'created_at']
    search_fields = ['name', 'member__username', 'phone']
    list_filter = ['resume_registered', 'created_at']
    list_per_page = 20
