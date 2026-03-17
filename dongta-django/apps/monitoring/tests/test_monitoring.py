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
