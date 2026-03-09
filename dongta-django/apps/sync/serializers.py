"""
apps/sync/serializers.py

동기화 상태 조회 API 직렬화기.
"""
from rest_framework import serializers

from .models import EventOutbox, SyncLog


class EventOutboxSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    event_type_display = serializers.CharField(source='get_event_type_display', read_only=True)

    class Meta:
        model = EventOutbox
        fields = [
            'id',
            'event_type',
            'event_type_display',
            'aggregate_type',
            'aggregate_id',
            'status',
            'status_display',
            'retry_count',
            'max_retries',
            'error_message',
            'created_at',
            'processed_at',
        ]
        read_only_fields = fields


class SyncLogSerializer(serializers.ModelSerializer):
    result_display = serializers.CharField(source='get_result_display', read_only=True)

    class Meta:
        model = SyncLog
        fields = [
            'id',
            'task_id',
            'started_at',
            'finished_at',
            'result',
            'result_display',
            'processed_count',
            'failed_count',
            'detail',
        ]
        read_only_fields = fields


class SyncStatusSerializer(serializers.Serializer):
    """동기화 현황 요약 직렬화기"""
    pending_count = serializers.IntegerField(read_only=True)
    processing_count = serializers.IntegerField(read_only=True)
    done_count = serializers.IntegerField(read_only=True)
    failed_count = serializers.IntegerField(read_only=True)
    dead_letter_count = serializers.IntegerField(read_only=True)
    last_sync_at = serializers.DateTimeField(allow_null=True, read_only=True)
