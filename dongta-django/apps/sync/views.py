"""
apps/sync/views.py

동기화 상태 모니터링 API (관리자 전용).
"""
import logging

from rest_framework import generics, permissions
from django.db.models import Count

from core.utils import success_response, error_response
from .models import EventOutbox, EventStatus, SyncLog
from .serializers import EventOutboxSerializer, SyncLogSerializer, SyncStatusSerializer

logger = logging.getLogger(__name__)


class SyncStatusView(generics.GenericAPIView):
    """
    GET /api/v1/sync/status/ — 동기화 현황 요약 (관리자 전용)

    PENDING / PROCESSING / DONE / FAILED / DEAD_LETTER 건수 반환
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        counts = EventOutbox.objects.values('status').annotate(cnt=Count('id'))
        status_map = {row['status']: row['cnt'] for row in counts}

        last_log = SyncLog.objects.order_by('-started_at').first()

        data = {
            'pending_count': status_map.get(EventStatus.PENDING, 0),
            'processing_count': status_map.get(EventStatus.PROCESSING, 0),
            'done_count': status_map.get(EventStatus.DONE, 0),
            'failed_count': status_map.get(EventStatus.FAILED, 0),
            'dead_letter_count': status_map.get(EventStatus.DEAD_LETTER, 0),
            'last_sync_at': last_log.started_at if last_log else None,
        }
        serializer = SyncStatusSerializer(data)
        return success_response(serializer.data)


class EventOutboxListView(generics.GenericAPIView):
    """
    GET /api/v1/sync/events/ — EventOutbox 목록 (관리자 전용)

    Query params:
        status  : pending | processing | done | failed | dead_letter
        page    : 페이지 번호 (default: 1)
        limit   : 페이지 크기 (default: 50)
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        queryset = EventOutbox.objects.all().order_by('-created_at')

        status_filter = request.query_params.get('status')
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 50))
        total = queryset.count()
        offset = (page - 1) * limit
        items = queryset[offset:offset + limit]

        serializer = EventOutboxSerializer(items, many=True)
        return success_response(
            serializer.data,
            meta={'page': page, 'total': total, 'limit': limit},
        )


class EventOutboxRetryView(generics.GenericAPIView):
    """
    POST /api/v1/sync/events/<pk>/retry/ — 실패 이벤트 재시도 (관리자 전용)
    """
    permission_classes = [permissions.IsAdminUser]

    def post(self, request, pk: int):
        try:
            outbox = EventOutbox.objects.get(pk=pk)
        except EventOutbox.DoesNotExist:
            return error_response('NOT_FOUND', '이벤트를 찾을 수 없습니다.', http_status=404)

        if outbox.status not in (EventStatus.FAILED, EventStatus.DEAD_LETTER):
            return error_response(
                'SYNC_001',
                f'재시도 불가 상태입니다. (현재 상태: {outbox.get_status_display()})',
            )

        # 상태 초기화 후 태스크 발행
        outbox.status = EventStatus.PENDING
        outbox.retry_count = 0
        outbox.error_message = ''
        outbox.save(update_fields=['status', 'retry_count', 'error_message'])

        from .tasks import process_event_outbox
        process_event_outbox.apply_async(args=[outbox.pk], queue='sync')

        logger.info('EventOutbox 수동 재시도 시작: id=%s by user=%s', pk, request.user)
        return success_response({'message': f'이벤트 {pk} 재시도를 시작했습니다.'})


class SyncLogListView(generics.GenericAPIView):
    """
    GET /api/v1/sync/logs/ — 동기화 실행 이력 (관리자 전용)
    """
    permission_classes = [permissions.IsAdminUser]

    def get(self, request):
        queryset = SyncLog.objects.all().order_by('-started_at')

        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 20))
        total = queryset.count()
        offset = (page - 1) * limit
        items = queryset[offset:offset + limit]

        serializer = SyncLogSerializer(items, many=True)
        return success_response(
            serializer.data,
            meta={'page': page, 'total': total, 'limit': limit},
        )
