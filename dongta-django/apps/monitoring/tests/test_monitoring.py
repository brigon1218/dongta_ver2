"""
Phase 2.1: 모니터링 API 단위 테스트
"""

from django.test import TestCase, RequestFactory
from django.core.cache import cache
from django.contrib.auth.models import User
from rest_framework.test import APITestCase
from rest_framework import status
from apps.monitoring.middleware import RoutingStatsMiddleware
from apps.monitoring.permissions import IsAdminUser


class RoutingStatsMiddlewareTestCase(TestCase):
    """RoutingStatsMiddleware 테스트"""

    def setUp(self):
        self.factory = RequestFactory()
        cache.clear()

    def test_middleware_increments_counter(self):
        """요청 카운트 증가 테스트"""
        request = self.factory.get('/api/v1/test/')
        middleware = RoutingStatsMiddleware(lambda r: None)

        # 중간값 처리하기 위해 get_response 모의
        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware_with_mock = RoutingStatsMiddleware(mock_get_response)
        middleware_with_mock(request)

        # 통계 확인
        stats = RoutingStatsMiddleware.get_hourly_stats()
        self.assertIn('GET', stats)

    def test_get_daily_stats(self):
        """일일 통계 조회 테스트"""
        stats = RoutingStatsMiddleware.get_daily_stats('20260317')
        # 빈 dict이거나 valid한 구조
        self.assertIsInstance(stats, dict)

    def test_get_hourly_stats(self):
        """시간별 통계 조회 테스트"""
        stats = RoutingStatsMiddleware.get_hourly_stats()
        self.assertIsInstance(stats, dict)


class IsAdminUserPermissionTestCase(TestCase):
    """IsAdminUser 권한 테스트"""

    def setUp(self):
        self.factory = RequestFactory()
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='test123'
        )
        self.regular_user = User.objects.create_user(
            username='user',
            email='user@test.com',
            password='test123'
        )

    def test_admin_user_permission(self):
        """Admin 사용자 권한 확인"""
        request = self.factory.get('/api/v1/monitoring/status/')
        request.user = self.admin_user

        permission = IsAdminUser()
        self.assertTrue(permission.has_permission(request, None))

    def test_regular_user_no_permission(self):
        """일반 사용자 권한 부재 확인"""
        request = self.factory.get('/api/v1/monitoring/status/')
        request.user = self.regular_user

        permission = IsAdminUser()
        self.assertFalse(permission.has_permission(request, None))

    def test_anonymous_user_no_permission(self):
        """익명 사용자 권한 부재 확인"""
        request = self.factory.get('/api/v1/monitoring/status/')
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()

        permission = IsAdminUser()
        self.assertFalse(permission.has_permission(request, None))


class MonitoringAPITestCase(APITestCase):
    """모니터링 API 엔드포인트 테스트"""

    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='test123'
        )
        self.client.login(username='admin', password='test123')

    def test_system_status_endpoint(self):
        """GET /api/v1/monitoring/status/ 테스트"""
        response = self.client.get('/api/v1/monitoring/status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('overall_status', response.json()['data'])

    def test_routing_stats_endpoint(self):
        """GET /api/v1/monitoring/routing/ 테스트"""
        response = self.client.get('/api/v1/monitoring/routing/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_requests', response.json()['data'])

    def test_bridge_stats_endpoint(self):
        """GET /api/v1/monitoring/bridge/ 테스트"""
        response = self.client.get('/api/v1/monitoring/bridge/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('bridge_auth', response.json()['data'])

    def test_event_status_endpoint(self):
        """GET /api/v1/monitoring/events/ 테스트"""
        response = self.client.get('/api/v1/monitoring/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('total_events', response.json()['data'])

    def test_unauthorized_access(self):
        """권한 없는 접근 테스트"""
        self.client.logout()
        response = self.client.get('/api/v1/monitoring/status/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_auth_stats_endpoint_alias(self):
        """GET /api/v1/monitoring/auth/ (bridge의 alias) 테스트"""
        response = self.client.get('/api/v1/monitoring/auth/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('bridge_auth', response.json()['data'])

    def test_system_status_includes_aggregate_stats(self):
        """SystemStatusView가 routing/auth_bridge/events 집계 정보를 포함하는지 확인"""
        response = self.client.get('/api/v1/monitoring/status/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('routing', data)
        self.assertIn('auth_bridge', data)
        self.assertIn('events', data)

    def test_routing_stats_with_hours_param(self):
        """GET /api/v1/monitoring/routing/?hours=3 테스트"""
        response = self.client.get('/api/v1/monitoring/routing/?hours=3')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('period', data)
        self.assertIn('last_3_hours', data['period'])

    def test_routing_stats_with_granularity_param(self):
        """GET /api/v1/monitoring/routing/?granularity=daily 테스트"""
        response = self.client.get('/api/v1/monitoring/routing/?granularity=daily')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('granularity', data)
        self.assertEqual(data['granularity'], 'daily')

    def test_event_status_with_limit_param(self):
        """GET /api/v1/monitoring/events/?limit=5 테스트"""
        response = self.client.get('/api/v1/monitoring/events/?limit=5')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('recent_events', data)
        self.assertIn('summary', data)
        self.assertLessEqual(len(data['recent_events']), 5)

    def test_event_status_summary_structure(self):
        """EventStatusView summary 구조 검증"""
        response = self.client.get('/api/v1/monitoring/events/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('summary', data)
        summary = data['summary']
        self.assertIn('total_events', summary)
        self.assertIn('by_status', summary)
        by_status = summary['by_status']
        self.assertIn('pending', by_status)
        self.assertIn('done', by_status)
        self.assertIn('failed', by_status)
        self.assertIn('dead_letter', by_status)

    def test_event_retry_not_found(self):
        """존재하지 않는 이벤트 재처리 시도"""
        response = self.client.post('/api/v1/monitoring/events/99999/retry/')
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class EventRetryAPITestCase(APITestCase):
    """EventRetryView 테스트"""

    def setUp(self):
        from apps.accounts.models import Member
        from apps.sync.models import EventOutbox, EventType, EventStatus

        self.admin_user = User.objects.create_superuser(
            username='admin2',
            email='admin2@test.com',
            password='test123'
        )
        self.client.login(username='admin2', password='test123')

        self.failed_event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_INSERT,
            aggregate_type='member',
            aggregate_id=1,
            payload={'memb_idx': 1},
            status=EventStatus.FAILED,
        )
        self.done_event = EventOutbox.objects.create(
            event_type=EventType.MEMBER_UPDATE,
            aggregate_type='member',
            aggregate_id=2,
            payload={'memb_idx': 2},
            status=EventStatus.DONE,
        )

    def test_retry_failed_event(self):
        """FAILED 이벤트 재처리"""
        response = self.client.post(
            f'/api/v1/monitoring/events/{self.failed_event.id}/retry/'
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()['data']
        self.assertIn('task_id', data)
        self.assertIn('event_id', data)

    def test_retry_non_retryable_event(self):
        """DONE 이벤트는 재처리 불가"""
        response = self.client.post(
            f'/api/v1/monitoring/events/{self.done_event.id}/retry/'
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_retry_requires_admin(self):
        """관리자만 재처리 가능"""
        self.client.logout()
        response = self.client.post(
            f'/api/v1/monitoring/events/{self.failed_event.id}/retry/'
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
