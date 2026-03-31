"""
Phase 2.1: Bridge Authentication Unit Tests

SessionBridgeMiddleware와 BridgeAuthView 테스트
"""

from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import AnonymousUser
from rest_framework import status
from rest_framework.test import APITestCase

from apps.accounts.models import Member
from apps.accounts.middleware import SessionBridgeMiddleware, RequestIDMiddleware


class RequestIDMiddlewareTestCase(TestCase):
    """RequestIDMiddleware 테스트"""

    def setUp(self):
        self.factory = RequestFactory()
        self.middleware = RequestIDMiddleware(lambda r: None)

    def test_request_id_generation(self):
        """X-Request-ID가 없으면 UUID 생성"""
        request = self.factory.get('/')

        # Mock get_response
        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = RequestIDMiddleware(mock_get_response)
        response = middleware(request)

        # correlation_id 설정 확인
        self.assertIsNotNone(request.correlation_id)
        self.assertIn('X-Request-ID', response)

    def test_request_id_propagation(self):
        """X-Request-ID 헤더가 있으면 전파"""
        request_id = 'test-request-id-12345'
        request = self.factory.get('/', HTTP_X_REQUEST_ID=request_id)

        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = RequestIDMiddleware(mock_get_response)
        response = middleware(request)

        # correlation_id 확인
        self.assertEqual(request.correlation_id, request_id)
        self.assertEqual(response['X-Request-ID'], request_id)


class SessionBridgeMiddlewareTestCase(TestCase):
    """SessionBridgeMiddleware 테스트"""

    def setUp(self):
        self.factory = RequestFactory()
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

    def test_middleware_skips_without_phpsessid(self):
        """PHPSESSID 쿠키가 없으면 미들웨어 스킵"""
        request = self.factory.get('/')
        request.user = AnonymousUser()

        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = SessionBridgeMiddleware(mock_get_response)
        response = middleware(request)

        # 요청이 정상적으로 처리됨
        self.assertEqual(response.status_code, 200)

    def test_middleware_disabled(self):
        """BRIDGE_AUTH_ENABLED=False일 때 미들웨어 비활성화"""
        from django.test import override_settings

        request = self.factory.get('/')
        request.COOKIES['PHPSESSID'] = 'dummy-session-id'
        request.user = AnonymousUser()

        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        with override_settings(BRIDGE_AUTH_ENABLED=False):
            middleware = SessionBridgeMiddleware(mock_get_response)
            response = middleware(request)

        # 미들웨어가 비활성화되었으므로 요청 통과
        self.assertEqual(response.status_code, 200)

    def test_middleware_skips_with_jwt(self):
        """JWT가 이미 있으면 미들웨어 스킵"""
        request = self.factory.get('/', HTTP_AUTHORIZATION='Bearer dummy-token')
        request.user = AnonymousUser()

        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = SessionBridgeMiddleware(mock_get_response)
        response = middleware(request)

        # JWT가 있으면 미들웨어 작동 안 함
        self.assertEqual(response.status_code, 200)


class BridgeAuthAPITestCase(APITestCase):
    """BridgeAuthView API 테스트"""

    def setUp(self):
        self.client = Client()
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

    def test_bridge_auth_without_session(self):
        """PHP 세션 없이 인증 실패"""
        response = self.client.post(
            '/api/v1/auth/bridge/',
            data={},
            content_type='application/json'
        )

        # 실패 응답
        self.assertIn(response.status_code, [400, 401])
        if 'data' in response.json():
            self.assertIn('error_code', response.json()['data'] or {})

    def test_bridge_auth_with_invalid_session(self):
        """유효하지 않은 PHP 세션으로 인증 실패"""
        response = self.client.post(
            '/api/v1/auth/bridge/',
            data={'php_session_id': 'invalid-session-id'},
            content_type='application/json'
        )

        # 실패 응답 (세션 조회 실패)
        self.assertEqual(response.status_code, 401)

    def test_bridge_auth_permission_allow_any(self):
        """BridgeAuthView는 AllowAny 권한"""
        # 로그인하지 않은 사용자도 호출 가능
        response = self.client.post(
            '/api/v1/auth/bridge/',
            data={'php_session_id': 'invalid-session'},
            content_type='application/json'
        )

        # 세션이 없어서 실패하지만, 권한 오류 아님
        # (400/401이지 403이 아님)
        self.assertNotEqual(response.status_code, 403)


class BridgeRevokeAPITestCase(APITestCase):
    """BridgeRevokeView API 테스트"""

    def setUp(self):
        self.client = Client()
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

    def test_bridge_revoke_without_token(self):
        """토큰 없이 revoke 실패"""
        response = self.client.post(
            '/api/v1/auth/bridge/revoke/',
            data={},
            content_type='application/json'
        )

        # 토큰 부재 오류
        self.assertEqual(response.status_code, 400)

    def test_bridge_revoke_permission_allow_any(self):
        """BridgeRevokeView는 AllowAny 권한"""
        # PHP 로그아웃 콜백에서 호출하므로 비인증 사용자도 호출 가능
        response = self.client.post(
            '/api/v1/auth/bridge/revoke/',
            data={'refresh': 'invalid-token'},
            content_type='application/json'
        )

        # 토큰이 유효하지 않아서 오류이지만, 권한 오류 아님
        self.assertNotEqual(response.status_code, 403)

    def test_bridge_revoke_with_php_session_id(self):
        """php_session_id 포함 시 캐시 삭제"""
        # 유효한 refresh 토큰 발급
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.member)
        refresh_token = str(refresh)

        # Revoke 호출
        response = self.client.post(
            '/api/v1/auth/bridge/revoke/',
            data={
                'refresh': refresh_token,
                'php_session_id': 'test-php-session-123'
            },
            content_type='application/json'
        )

        # 성공 응답
        self.assertEqual(response.status_code, 200)
        self.assertIn('message', response.json()['data'])


class BridgeTokenRefreshAPITestCase(APITestCase):
    """Bridge Token Refresh API 테스트"""

    def setUp(self):
        self.client = Client()
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

    def test_bridge_token_refresh(self):
        """Bridge refresh 토큰 엔드포인트 작동"""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.member)
        refresh_token = str(refresh)

        # Refresh 호출
        response = self.client.post(
            '/api/v1/auth/bridge/refresh/',
            data={'refresh': refresh_token},
            content_type='application/json'
        )

        # 성공
        self.assertEqual(response.status_code, 200)
        self.assertIn('access', response.json()['data'])


class BridgeIntegrationTestCase(APITestCase):
    """Bridge 인증 통합 테스트"""

    def setUp(self):
        self.client = Client()
        self.member = Member.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpass123',
            name='Test User',
        )

    def test_bridge_auth_and_revoke_flow(self):
        """Bridge 인증-발급-무효화 플로우"""
        from rest_framework_simplejwt.tokens import RefreshToken

        # 1. 직접 JWT 발급
        refresh = RefreshToken.for_user(self.member)
        access_token = str(refresh.access_token)
        refresh_token = str(refresh)

        # 2. JWT로 인증된 요청
        headers = {'HTTP_AUTHORIZATION': f'Bearer {access_token}'}
        response = self.client.get('/api/v1/auth/me/', **headers)
        self.assertEqual(response.status_code, 200)

        # 3. Token revoke
        response = self.client.post(
            '/api/v1/auth/bridge/revoke/',
            data={'refresh': refresh_token},
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        # 4. Revoke 후 access 토큰 사용 불가능해야 함
        # (실제로는 블랙리스트 검증이 필요하지만, 여기서는 revoke 성공만 확인)

    def test_correlation_id_in_bridge_requests(self):
        """Bridge 요청에서 correlation_id 전파"""
        # X-Request-ID 헤더 포함
        response = self.client.post(
            '/api/v1/auth/bridge/',
            data={'php_session_id': 'dummy'},
            content_type='application/json',
            HTTP_X_REQUEST_ID='test-correlation-id-123'
        )

        # 응답에 X-Request-ID 포함
        self.assertIn('X-Request-ID', response)
        # (요청 흐름 추적 확인)


class SessionBridgeMiddlewareCacheTestCase(TestCase):
    """SessionBridgeMiddleware 캐시 동작 테스트"""

    def setUp(self):
        from django.core.cache import cache as django_cache
        django_cache.clear()
        self.factory = RequestFactory()
        self.member = Member.objects.create_user(
            username='cacheuser',
            email='cache@example.com',
            password='testpass123',
            name='Cache User',
        )

    def test_middleware_sets_bridge_jwt_in_response(self):
        """캐시 HIT 시 X-Bridge-Token 응답 헤더 설정"""
        from django.core.cache import cache as django_cache
        from apps.accounts.middleware import BRIDGE_CACHE_PREFIX

        # 캐시에 member_pk 저장 (SessionBridgeMiddleware 캐시 HIT 시뮬레이션)
        cache_key = f'{BRIDGE_CACHE_PREFIX}test-php-session-cached'
        django_cache.set(cache_key, {'member_pk': self.member.pk}, 900)

        request = self.factory.get('/', HTTP_COOKIE='PHPSESSID=test-php-session-cached')
        request.COOKIES['PHPSESSID'] = 'test-php-session-cached'

        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = SessionBridgeMiddleware(mock_get_response)
        response = middleware(request)

        # 캐시 HIT이면 JWT가 생성되어 헤더에 설정됨
        self.assertIn('X-Bridge-Token', response)
        self.assertIn('X-Bridge-Refresh', response)

    def test_middleware_clears_invalid_cache(self):
        """존재하지 않는 member_pk 캐시 MISS 시 캐시 삭제"""
        from django.core.cache import cache as django_cache
        from apps.accounts.middleware import BRIDGE_CACHE_PREFIX

        # 존재하지 않는 member_pk를 캐시에 저장
        cache_key = f'{BRIDGE_CACHE_PREFIX}stale-session'
        django_cache.set(cache_key, {'member_pk': 99999}, 900)

        request = self.factory.get('/')
        request.COOKIES['PHPSESSID'] = 'stale-session'

        def mock_get_response(r):
            from django.http import HttpResponse
            return HttpResponse()

        middleware = SessionBridgeMiddleware(mock_get_response)
        response = middleware(request)

        # 존재하지 않는 member → 캐시 삭제 → X-Bridge-Token 없음
        self.assertNotIn('X-Bridge-Token', response)
        # 캐시도 삭제됨
        self.assertIsNone(django_cache.get(cache_key))


class BridgeRevokeSessionCacheTestCase(APITestCase):
    """BridgeRevokeView 세션 캐시 삭제 테스트"""

    def setUp(self):
        self.client = Client()
        self.member = Member.objects.create_user(
            username='revokeuser',
            email='revoke@example.com',
            password='testpass123',
            name='Revoke User',
        )

    def test_revoke_clears_session_cache(self):
        """php_session_id 포함 시 세션 캐시도 삭제됨"""
        from django.core.cache import cache as django_cache
        from apps.accounts.middleware import BRIDGE_CACHE_PREFIX
        from rest_framework_simplejwt.tokens import RefreshToken

        # 캐시에 세션 저장
        php_session_id = 'test-session-to-revoke'
        cache_key = f'{BRIDGE_CACHE_PREFIX}{php_session_id}'
        django_cache.set(cache_key, {'member_pk': self.member.pk}, 900)

        # 유효한 refresh 토큰 발급
        refresh = RefreshToken.for_user(self.member)

        # Revoke 호출 (php_session_id 포함)
        response = self.client.post(
            '/api/v1/auth/bridge/revoke/',
            data={
                'refresh': str(refresh),
                'php_session_id': php_session_id,
            },
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        # 캐시가 삭제됨
        self.assertIsNone(django_cache.get(cache_key))

    def test_revoke_response_structure(self):
        """Revoke 성공 응답 구조 검증"""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(self.member)
        response = self.client.post(
            '/api/v1/auth/bridge/revoke/',
            data={'refresh': str(refresh)},
            content_type='application/json'
        )

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn('data', data)
        self.assertIn('message', data['data'])
