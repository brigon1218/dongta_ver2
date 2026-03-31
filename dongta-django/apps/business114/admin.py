from django.contrib import admin
from .models import Business


@admin.register(Business)
class BusinessAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'corp_name', 'industry_type', 'business_type', 
        'member', 'is_approved', 'view_count', 'created_at'
    ]
    list_filter = ['is_approved', 'industry_type', 'business_type', 'created_at']
    search_fields = ['corp_name', 'member__username', 'keywords', 'phone']
    actions = ['approve_businesses']

    def approve_businesses(self, request, queryset):
        queryset.update(is_approved=True)
    approve_businesses.short_description = "선택된 업체 승인"
