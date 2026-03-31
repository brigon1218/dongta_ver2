from django.contrib import admin
from apps.sync.models import EventOutbox


@admin.register(EventOutbox)
class EventOutboxAdmin(admin.ModelAdmin):
    list_display = ['id', 'event_type', 'source', 'status', 'retry_count', 'created_at']
    list_filter = ['status', 'source', 'event_type']
    search_fields = ['event_type', 'aggregate_id']
    readonly_fields = ['id', 'created_at', 'updated_at']
    actions = ['retry_events']

    @admin.action(description='선택된 이벤트 재처리 (상태를 pending으로 초기화)')
    def retry_events(self, request, queryset):
        count = queryset.update(status='pending', retry_count=0)
        self.message_user(request, f'{count}개의 이벤트가 재처리 대기 상태로 변경되었습니다.')
