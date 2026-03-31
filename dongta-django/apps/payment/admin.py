from django.contrib import admin
from .models import PointAccount, PaymentHistory


@admin.register(PointAccount)
class PointAccountAdmin(admin.ModelAdmin):
    list_display = ['member', 'total_charged', 'total_used', 'balance', 'last_charged_at']
    search_fields = ['member__username', 'member__email']
    readonly_fields = ['balance']
    list_per_page = 20


@admin.register(PaymentHistory)
class PaymentHistoryAdmin(admin.ModelAdmin):
    list_display = [
        'id', 'member', 'amount', 'point_amount',
        'pay_method', 'status', 'is_success',
        'tid', 'confirmed_at', 'created_at',
    ]
    list_filter = ['status', 'is_success', 'pay_method']
    search_fields = ['member__username', 'member__email', 'tid', 'danal_order_id']
    list_per_page = 20
    readonly_fields = ['tid', 'danal_order_id', 'danal_response', 'created_at', 'updated_at']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
