"""
Phase 2.1: 모니터링 미들웨어
RoutingStatsMiddleware - Django 요청 통계 수집
"""

import logging
from django.core.cache import cache
from django.utils import timezone

logger = logging.getLogger(__name__)


class RoutingStatsMiddleware:
    """
    모든 Django 요청을 카운트하여 Redis에 저장.
    시간별, HTTP 메서드별 통계 수집.

    데이터 구조:
    - routing:django:{YYYYMMDD}:{HH}:{METHOD} = count
    예: routing:django:20260317:14:GET = 100
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        try:
            now = timezone.now()
            date_key = now.strftime('%Y%m%d')
            hour_key = now.strftime('%H')
            method = request.method

            # Redis key: routing:django:20260317:14:GET
            redis_key = f'routing:django:{date_key}:{hour_key}:{method}'

            # Atomic increment (48시간 유지)
            try:
                cache.incr(redis_key)
                # 첫 번째 요청이면 TTL 설정
                ttl = cache.ttl(redis_key)
                if ttl == -1:  # TTL 없음
                    cache.set(redis_key, cache.get(redis_key), timeout=172800)  # 48시간
            except ValueError:
                # Key가 없으면 새로 생성
                cache.set(redis_key, 1, timeout=172800)

        except Exception as e:
            logger.warning('RoutingStatsMiddleware failed: %s', str(e))

        return response

    @staticmethod
    def get_daily_stats(date_str=None):
        """
        날짜별 통계 조회 (YYYYMMDD 형식)
        예: '20260317'
        """
        if not date_str:
            date_str = timezone.now().strftime('%Y%m%d')

        stats = {}
        for hour in range(24):
            hour_str = f'{hour:02d}'
            hour_data = {}

            for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
                redis_key = f'routing:django:{date_str}:{hour_str}:{method}'
                count = cache.get(redis_key, 0)
                if count:
                    hour_data[method] = count

            if hour_data:
                stats[hour_str] = hour_data

        return stats

    @staticmethod
    def get_hourly_stats():
        """현재 시간의 통계 조회"""
        now = timezone.now()
        date_str = now.strftime('%Y%m%d')
        hour_str = now.strftime('%H')

        stats = {}
        for method in ['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS', 'HEAD']:
            redis_key = f'routing:django:{date_str}:{hour_str}:{method}'
            count = cache.get(redis_key, 0)
            if count:
                stats[method] = count

        return stats
