"""
Phase 2.1: 모니터링 API Views
- SystemStatusView: 전체 시스템 상태
- RoutingStatsView: Django/PHP 트래픽 통계
- BridgeAuthStatsView: 세션 브리지 통계
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

        return success_response({
            'timestamp': timezone.now().isoformat(),
            'overall_status': overall_status,
            'components': health,
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


class RoutingStatsView(views.APIView):
    """
    GET /api/v1/monitoring/routing/
    Django 요청 통계 (PHP는 Nginx log 기준)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        # 쿼리 파라미터: date (YYYYMMDD 형식, 기본: 오늘)
        date_str = request.query_params.get('date')

        if date_str:
            stats = RoutingStatsMiddleware.get_daily_stats(date_str)
            period = f'daily ({date_str})'
        else:
            stats = RoutingStatsMiddleware.get_hourly_stats()
            period = 'hourly (current hour)'

        # 총 요청 수
        total_requests = sum(
            sum(hour_data.values())
            for hour_data in (stats.values() if isinstance(stats, dict) else [])
        )

        return success_response({
            'timestamp': timezone.now().isoformat(),
            'period': period,
            'total_requests': total_requests,
            'breakdown_by_method': stats,
            'note': 'PHP 트래픽은 Nginx access log에서 별도 집계 필요',
        })


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
    이벤트 로깅 상태 (Phase 2.2 준비)
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        try:
            from apps.sync.models import EventOutbox

            # 이벤트 상태별 통계
            total = EventOutbox.objects.count()
            pending = EventOutbox.objects.filter(status='pending').count()
            processing = EventOutbox.objects.filter(status='processing').count()
            completed = EventOutbox.objects.filter(status='completed').count()
            failed = EventOutbox.objects.filter(status='failed').count()

            return success_response({
                'timestamp': timezone.now().isoformat(),
                'total_events': total,
                'by_status': {
                    'pending': pending,
                    'processing': processing,
                    'completed': completed,
                    'failed': failed,
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
