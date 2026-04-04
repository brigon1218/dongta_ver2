from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Member, MemberDormant


@admin.register(Member)
class MemberAdmin(admin.ModelAdmin):
    list_display = ['username', 'name', 'email', 'level', 'region', 'login_count',
                    'is_active', 'is_deleted', 'created_at']
    list_filter = ['level', 'region', 'is_active', 'is_overseas', 'is_deleted']
    list_per_page = 20
    search_fields = ['username', 'name', 'email', 'phone']
    ordering = ['-created_at']

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('개인정보', {'fields': ('name', 'email', 'phone', 'landline')}),
        ('주소', {'fields': ('postal_code', 'address', 'region')}),
        ('회원정보', {'fields': ('level', 'member_type', 'corp_name', 'point')}),
        ('설정', {'fields': ('email_opt_in', 'is_overseas', 'overseas_approved')}),
        ('소셜로그인', {'fields': ('google_id', 'naver_id')}),
        ('권한', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_deleted')}),
        ('활동', {'fields': ('last_login_at', 'login_count', 'reg_ip')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'name', 'email', 'password1', 'password2'),
        }),
    )


@admin.register(MemberDormant)
class MemberDormantAdmin(admin.ModelAdmin):
    list_display = ['member', 'dormant_since', 'created_at']
    search_fields = ['member__username', 'member__name']
    list_per_page = 20
