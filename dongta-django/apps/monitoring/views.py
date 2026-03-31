"""
Phase 2.1: 모니터링 API Views
- SystemStatusView: 전체 시스템 상태 (집계 대시보드 포함)
- RoutingStatsView: Django/PHP 트래픽 통계 (hours/granularity 파라미터 지원)
- BridgeAuthStatsView: 세션 브리지 통계 (/bridge/ 및 /auth/ 경로)
- EventStatusView: 이벤트 처리 현황 (최근 이벤트 목록 포함)
- EventRetryView: 이벤트 재처리 트리거
"""

import logging
from rest_framework import views, status
from django.core.cache import cache
from django.db import connections
from django.utils import timezone
from core.utils import success_response, error_response
from .permissions import IsAdminUser
from .middleware import RoutingStatsMiddleware

logger = logging.getLogger(__name__)


class SystemStatusView(views.APIView):
    """
    GET /api/v1/monitoring/status/
    전체 시스템 상태 확인 (DB, Redis, Celery 등)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        health = {}

        # Django
        health['django'] = {'status': 'healthy', 'message': '응답 가능'}

        # PostgreSQL
        health['postgresql'] = self._check_postgresql()

        # Redis
        health['redis'] = self._check_redis()

        # Legacy MySQL
        health['mysql_legacy'] = self._check_mysql_legacy()

        # Celery
        health['celery'] = self._check_celery()

        # 전체 상태
        overall_status = 'healthy' if all(
            item.get('status') == 'healthy'
            for item in health.values()
        ) else 'degraded'

        # Design S7.1: 집계 대시보드 — routing, auth_bridge, events 인라인 포함
        today = timezone.now().strftime('%Y-%m-%d')
        routing_stats = RoutingStatsMiddleware.get_hourly_stats()
        routing_total = sum(routing_stats.values()) if routing_stats else 0

        bridge_success = cache.get(f'bridge:success:{today}', 0)
        bridge_fail = cache.get(f'bridge:fail:{today}', 0)
        bridge_total = bridge_success + bridge_fail

        event_summary = self._get_event_summary()

        return success_response({
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall_status,
            'components': health,
            # Design 요구: 집계 정보 인라인 포함
            'routing': {
                'current_hour_requests': routing_total,
                'breakdown': routing_stats,
            },
            'auth_bridge': {
                'today_success': bridge_success,
                'today_failed': bridge_fail,
                'today_total': bridge_total,
                'success_rate_percent': round(bridge_success / bridge_total * 100, 2) if bridge_total > 0 else 0,
            },
            'events': event_summary,
        })

    @staticmethod
    def _check_postgresql():
        """PostgreSQL 연결 확인"""
        try:
            from django.db import connection
            connection.ensure_connection()
            return {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            logger.error('PostgreSQL health check failed: %s', str(e))
            return {'status': 'unhealthy', 'message': str(e)}

    @staticmethod
    def _check_redis():
        """Redis 연결 확인"""
        try:
            cache.set('health:check', 'ok', timeout=10)
            value = cache.get('health:check')
            if value == 'ok':
                return {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            logger.error('Redis health check failed: %s', str(e))
            return {'status': 'unhealthy', 'message': str(e)}

    @staticmethod
    def _check_mysql_legacy():
        """Legacy MySQL 연결 확인"""
        try:
            with connections['legacy'].cursor() as cursor:
                cursor.execute('SELECT 1')
                return {'status': 'healthy', 'message': 'Connected'}
        except Exception as e:
            logger.warning('MySQL legacy health check failed: %s', str(e))
            return {'status': 'unhealthy', 'message': str(e)}

    @staticmethod
    def _check_celery():
        """Celery 워커 상태 확인 (timeout 포함)"""
        try:
            from celery import current_app
            from celery.app.control import Inspect
            import socket

            inspect = Inspect(app=current_app)
            try:
                # 2초 timeout
                stats = inspect.stats(timeout=2)
                if stats:
                    return {'status': 'healthy', 'message': f'Workers: {len(stats)}'}
                else:
                    return {'status': 'unknown', 'message': 'No workers responding'}
            except socket.timeout:
                return {'status': 'unknown', 'message': 'Celery inspect timeout'}
        except Exception as e:
            logger.warning('Celery health check failed: %s', str(e))
            return {'status': 'unknown', 'message': str(e)}

    @staticmethod
    def _get_event_summary():
        """이벤트 아웃박스 요약 정보 조회"""
        try:
            from apps.sync.models import EventOutbox
            total = EventOutbox.objects.count()
            pending = EventOutbox.objects.filter(status='pending').count()
            failed = EventOutbox.objects.filter(status='failed').count()
            dead_letter = EventOutbox.objects.filter(status='dead_letter').count()
            return {
                'total': total,
                'pending': pending,
                'failed': failed,
                'dead_letter': dead_letter,
            }
        except Exception:
            return {'total': 0, 'pending': 0, 'failed': 0, 'dead_letter': 0}


class RoutingStatsView(views.APIView):
    """
    GET /api/v1/monitoring/routing/
    Django 요청 통계 (PHP는 Nginx log 기준)

    Query Parameters:
        date (str): YYYYMMDD 형식 날짜 (기본: 오늘)
        hours (int): 최근 N시간 통계 (1-24, date와 상호 배타적)
        granularity (str): 'hourly' | 'daily' (기본: 자동 판단)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # Design S7.2: hours, granularity 파라미터 지원
        date_str = request.query_params.get('date')
        hours_param = request.query_params.get('hours')
        granularity = request.query_params.get('granularity', 'auto')

        if hours_param:
            # 최근 N시간 통계
            try:
                hours = min(max(int(hours_param), 1), 24)
            except (ValueError, TypeError):
                hours = 1
            stats = self._get_recent_hours_stats(hours)
            period = f'last_{hours}_hours'
            total_requests = sum(
                sum(h.values()) if isinstance(h, dict) else h
                for h in stats.values()
            )
        elif date_str or granularity == 'daily':
            if not date_str:
                date_str = timezone.now().strftime('%Y%m%d')
            stats = RoutingStatsMiddleware.get_daily_stats(date_str)
            period = f'daily ({date_str})'
            total_requests = sum(
                sum(hour_data.values())
                for hour_data in (stats.values() if isinstance(stats, dict) else [])
            )
        else:
            # 기본: 현재 시간 통계
            stats = RoutingStatsMiddleware.get_hourly_stats()
            period = 'hourly (current hour)'
            total_requests = sum(stats.values()) if isinstance(stats, dict) else 0

        return success_response({
            'timestamp': timezone.now().isoformat(),
            'period': period,
            'granularity': granularity if granularity != 'auto' else ('hourly' if not hours_param and not date_str else 'daily'),
            'total_requests': total_requests,
            'breakdown_by_method': stats,
            'note': 'PHP 트래픽은 Nginx access log에서 별도 집계 필요',
        })

    @staticmethod
    def _get_recent_hours_stats(hours):
        """최근 N시간 통계를 시간별로 수집"""
        now = timezone.now()
        result = {}
        for delta in range(hours):
            target = now - timezone.timedelta(hours=delta)
            date_str = target.strftime('%Y%m%d')
            hour_str = target.strftime('%H')
            hour_data = {}
            for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']:
                redis_key = f'routing:django:{date_str}:{hour_str}:{method}'
                count = cache.get(redis_key, 0)
                if count:
                    hour_data[method] = count
            if hour_data:
                result[f'{date_str}_{hour_str}'] = hour_data
        return result


class BridgeAuthStatsView(views.APIView):
    """
    GET /api/v1/monitoring/bridge/
    세션 브리지 인증 성공률 및 통계
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        today = timezone.now().strftime('%Y-%m-%d')

        # 오늘의 브리지 성공 횟수
        bridge_success_key = f'bridge:success:{today}'
        bridge_revoke_key = f'bridge:revoke:{today}'
        bridge_fail_key = f'bridge:fail:{today}'

        success_count = cache.get(bridge_success_key, 0)
        revoke_count = cache.get(bridge_revoke_key, 0)
        fail_count = cache.get(bridge_fail_key, 0)

        total = success_count + fail_count
        success_rate = (success_count / total * 100) if total > 0 else 0

        return success_response({
            'timestamp': timezone.now().isoformat(),
            'date': today,
            'bridge_auth': {
                'success': success_count,
                'revoked': revoke_count,
                'failed': fail_count,
                'total': total,
                'success_rate_percent': round(success_rate, 2),
            },
            'cache_keys': {
                'success': bridge_success_key,
                'revoked': bridge_revoke_key,
                'failed': bridge_fail_key,
            },
        })


class EventStatusView(views.APIView):
    """
    GET /api/v1/monitoring/events/
    이벤트 로깅 현황 — 상태별 통계 + 최근 이벤트 + 필터링

    Query Parameters:
        event_type (str): 이벤트 유형 필터 (예: member.insert)
        status_filter (str): 상태 필터 (pending, failed, dead_letter)
        limit (int): 최근 이벤트 수 (기본 10, 최대 50)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from apps.sync.models import EventOutbox, EventStatus

            # 필터링 파라미터
            event_type_filter = request.query_params.get('event_type')
            status_filter = request.query_params.get('status_filter')
            try:
                limit = min(max(int(request.query_params.get('limit', 10)), 1), 50)
            except (ValueError, TypeError):
                limit = 10

            qs = EventOutbox.objects.all()

            # 이벤트 상태별 통계 (전체 기준)
            total = qs.count()
            pending = qs.filter(status=EventStatus.PENDING).count()
            processing = qs.filter(status=EventStatus.PROCESSING).count()
            done = qs.filter(status=EventStatus.DONE).count()
            failed = qs.filter(status=EventStatus.FAILED).count()
            dead_letter = qs.filter(status=EventStatus.DEAD_LETTER).count()

            # 필터 적용
            if event_type_filter:
                qs = qs.filter(event_type=event_type_filter)
            if status_filter:
                qs = qs.filter(status=status_filter)

            # 최근 이벤트 목록 (Design S7.3 요구사항)
            recent_events = list(
                qs.order_by('-created_at')[:limit].values(
                    'id', 'event_type', 'aggregate_type', 'aggregate_id',
                    'status', 'retry_count', 'source', 'created_at', 'processed_at',
                )
            )
            # datetime 직렬화
            for e in recent_events:
                if e.get('created_at'):
                    e['created_at'] = e['created_at'].isoformat()
                if e.get('processed_at'):
                    e['processed_at'] = e['processed_at'].isoformat()

            return success_response({
                'timestamp': timezone.now().isoformat(),
                'summary': {
                    'total_events': total,
                    'by_status': {
                        'pending': pending,
                        'processing': processing,
                        'done': done,
                        'failed': failed,
                        'dead_letter': dead_letter,
                    },
                    'pending_percentage': round((pending / total * 100) if total > 0 else 0, 2),
                    'failure_rate_percent': round(
                        ((failed + dead_letter) / total * 100) if total > 0 else 0, 2
                    ),
                },
                'recent_events': recent_events,
                'filters_applied': {
                    'event_type': event_type_filter,
                    'status': status_filter,
                    'limit': limit,
                },
                # Legacy 호환: 최상위에도 total_events 유지
                'total_events': total,
                'by_status': {
                    'pending': pending,
                    'processing': processing,
                    'done': done,
                    'failed': failed,
                    'dead_letter': dead_letter,
                },
                'pending_percentage': round((pending / total * 100) if total > 0 else 0, 2),
            })
        except Exception as e:
            logger.error('Event status check failed: %s', str(e))
            return error_response(
                'MONITOR_001',
                '이벤트 상태 조회 실패',
                details={'error': str(e)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class EventRetryView(views.APIView):
    """
    POST /api/v1/monitoring/events/{event_id}/retry/
    실패한 이벤트 재처리 트리거 (Design S7.3)

    DEAD_LETTER 또는 FAILED 상태의 이벤트를 PENDING으로 복구하여 재처리.
    """
    permission_classes = [IsAdminUser]

    def post(self, request, event_id):
        try:
            from apps.sync.models import EventOutbox, EventStatus

            try:
                event = EventOutbox.objects.get(pk=event_id)
            except EventOutbox.DoesNotExist:
                return error_response(
                    'MONITOR_002',
                    f'이벤트를 찾을 수 없습니다: id={event_id}',
                    http_status=status.HTTP_404_NOT_FOUND,
                )

            if event.status not in (EventStatus.FAILED, EventStatus.DEAD_LETTER):
                return error_response(
                    'MONITOR_003',
                    f'재시도 불가 상태입니다: status={event.status}',
                    details={'current_status': event.status, 'retryable': ['failed', 'dead_letter']},
                    http_status=status.HTTP_400_BAD_REQUEST,
                )

            # PENDING으로 복구 후 즉시 처리 태스크 발행
            event.status = EventStatus.PENDING
            event.retry_count = 0
            event.error_message = ''
            event.save(update_fields=['status', 'retry_count', 'error_message'])

            # Celery 태스크 즉시 발행
            from apps.sync.tasks import process_event_outbox
            task = process_event_outbox.apply_async(args=[event.id], queue='sync')

            logger.info(
                'Event retry triggered by admin: event_id=%s task_id=%s',
                event_id,
                task.id,
            )

            return success_response({
                'event_id': event_id,
                'new_status': EventStatus.PENDING,
                'task_id': task.id,
                'message': f'이벤트 {event_id} 재처리를 시작했습니다.',
            })

        except Exception as e:
            logger.error('Event retry failed: event_id=%s error=%s', event_id, str(e))
            return error_response(
                'MONITOR_004',
                '이벤트 재처리 실패',
                details={'error': str(e)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
