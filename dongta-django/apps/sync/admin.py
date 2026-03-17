"""
Phase 2.1: Event Logging Admin

EventOutbox와 SyncLog 관리자 페이지
"""

from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Q

from .models import EventOutbox, EventStatus, EventType, SyncLog


@admin.register(EventOutbox)
class EventOutboxAdmin(admin.ModelAdmin):
    """EventOutbox 관리자"""

    list_display = (
        'id',
        'event_type_display',
        'aggregate_type',
        'aggregate_id',
        'status_display',
        'created_at',
        'processed_at',
    )
    list_filter = ('status', 'event_type', 'aggregate_type', 'created_at')
    search_fields = ('event_type', 'aggregate_type', 'correlation_id')
    readonly_fields = (
        'id',
        'event_type',
        'aggregate_type',
        'aggregate_id',
        'payload',
        'source',
        'correlation_id',
        'status',
        'created_at',
        'processed_at',
        'retry_count',
        'error_message',
    )
    ordering = ['-created_at']

    fieldsets = (
        ('기본 정보', {
            'fields': ('id', 'event_type', 'aggregate_type', 'aggregate_id')
        }),
        ('페이로드', {
            'fields': ('payload',),
            'classes': ('collapse',)
        }),
        ('처리 상태', {
            'fields': ('status', 'retry_count', 'max_retries', 'error_message')
        }),
        ('추적 정보', {
            'fields': ('source', 'correlation_id'),
            'classes': ('collapse',)
        }),
        ('타임스탬프', {
            'fields': ('created_at', 'processed_at'),
            'classes': ('collapse',)
        }),
    )

    def event_type_display(self, obj):
        """이벤트 타입 표시"""
        choices_dict = dict(EventType.choices)
        return choices_dict.get(obj.event_type, obj.event_type)
    event_type_display.short_description = '이벤트 타입'
    event_type_display.admin_order_field = 'event_type'

    def status_display(self, obj):
        """상태를 색상으로 표시"""
        colors = {
            EventStatus.PENDING: '#FFA500',      # 주황색
            EventStatus.PROCESSING: '#87CEEB',  # 하늘색
            EventStatus.DONE: '#90EE90',        # 연두색
            EventStatus.FAILED: '#FFB6C1',      # 분홍색
            EventStatus.DEAD_LETTER: '#FF0000', # 빨강색
        }
        color = colors.get(obj.status, '#808080')
        status_label = obj.get_status_display()
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 3px; color: white;">{}</span>',
            color,
            status_label
        )
    status_display.short_description = '상태'
    status_display.admin_order_field = 'status'

    def get_queryset(self, request):
        """쿼리셋 최적화"""
        return super().get_queryset(request).select_related()

    def has_add_permission(self, request):
        """추가 권한 비활성화 (Signal에 의해서만 생성)"""
        return False

    def has_delete_permission(self, request, obj=None):
        """삭제 권한 비활성화 (감사 추적 목적)"""
        return False

    actions = ['mark_processing', 'mark_done', 'mark_failed_reset']

    def mark_processing(self, request, queryset):
        """선택된 이벤트를 PROCESSING으로 변경"""
        updated = queryset.filter(status__in=[EventStatus.PENDING, EventStatus.FAILED]).update(
            status=EventStatus.PROCESSING
        )
        self.message_user(request, f'{updated}개 이벤트가 처리 중으로 변경되었습니다.')
    mark_processing.short_description = '선택된 이벤트를 처리 중으로 변경'

    def mark_done(self, request, queryset):
        """선택된 이벤트를 DONE으로 변경"""
        from django.utils import timezone
        updated = queryset.filter(status=EventStatus.PROCESSING).update(
            status=EventStatus.DONE,
            processed_at=timezone.now()
        )
        self.message_user(request, f'{updated}개 이벤트가 완료로 변경되었습니다.')
    mark_done.short_description = '선택된 이벤트를 완료로 변경'

    def mark_failed_reset(self, request, queryset):
        """DEAD_LETTER 이벤트를 PENDING으로 복구"""
        updated = queryset.filter(status=EventStatus.DEAD_LETTER).update(
            status=EventStatus.PENDING,
            retry_count=0,
            error_message=''
        )
        self.message_user(request, f'{updated}개 이벤트가 재처리 대기 상태로 복구되었습니다.')
    mark_failed_reset.short_description = '선택된 DLQ 이벤트를 재처리 대기로 복구'


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    """SyncLog 관리자"""

    list_display = (
        'task_id',
        'result_display',
        'processed_count',
        'failed_count',
        'started_at',
        'finished_at',
    )
    list_filter = ('result', 'started_at')
    search_fields = ('task_id', 'detail')
    readonly_fields = (
        'task_id',
        'started_at',
        'finished_at',
        'result',
        'processed_count',
        'failed_count',
        'detail',
    )
    ordering = ['-started_at']

    fieldsets = (
        ('작업 정보', {
            'fields': ('task_id', 'result')
        }),
        ('처리 통계', {
            'fields': ('processed_count', 'failed_count')
        }),
        ('타임스탬프', {
            'fields': ('started_at', 'finished_at')
        }),
        ('상세 로그', {
            'fields': ('detail',),
            'classes': ('collapse',)
        }),
    )

    def result_display(self, obj):
        """결과를 색상으로 표시"""
        colors = {
            'success': '#90EE90',      # 연두색
            'partial': '#FFA500',      # 주황색
            'failure': '#FF0000',      # 빨강색
        }
        color = colors.get(obj.result, '#808080')
        result_label = obj.get_result_display()
        return format_html(
            '<span style="background-color: {}; padding: 3px 8px; border-radius: 3px; color: white;">{}</span>',
            color,
            result_label
        )
    result_display.short_description = '결과'
    result_display.admin_order_field = 'result'

    def has_add_permission(self, request):
        """추가 권한 비활성화 (Celery 태스크에 의해서만 생성)"""
        return False

    def has_delete_permission(self, request, obj=None):
        """삭제 권한 비활성화 (감사 추적 목적)"""
        return False
