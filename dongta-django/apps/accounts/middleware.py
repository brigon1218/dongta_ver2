"""
Phase 2.1: PHP ↔ Django 하이브리드 연동 미들웨어
- RequestIDMiddleware: X-Request-ID 생성 및 전파
- SessionBridgeMiddleware: PHP PHPSESSID → Django JWT 자동 변환
"""

import logging
import uuid
from django.conf import settings
from django.core.cache import cache
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

BRIDGE_CACHE_PREFIX = 'session:bridge:'
BRIDGE_CACHE_TTL = 900  # 15분


class RequestIDMiddleware:
    """
    X-Request-ID 헤더가 없으면 생성하여 전파.
    모든 로그에 correlation_id로 사용.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request_id = request.META.get('HTTP_X_REQUEST_ID')
        if not request_id:
            request_id = str(uuid.uuid4())
        request.correlation_id = request_id
        response = self.get_response(request)
        response['X-Request-ID'] = request_id
        return response


class SessionBridgeMiddleware:
    """
    PHP PHPSESSID 쿠키 -> Django JWT 자동 매핑.

    동작 플로우:
    1. PHPSESSID 쿠키 확인
    2. Authorization 헤더가 이미 있으면 SKIP
    3. Redis 캐시 조회 (session:bridge:{PHPSESSID})
    4. 캐시 MISS → MySQL legacy DB에서 세션 소유자 조회
    5. Django Member 매핑 (username 기준)
    6. JWT 생성 & Redis 캐시 저장
    7. request.user 설정
    """
    def __init__(self, get_response):
        self.get_response = get_response
        self.enabled = getattr(settings, 'BRIDGE_AUTH_ENABLED', True)

    def __call__(self, request):
        if not self.enabled:
            return self.get_response(request)

        # JWT가 이미 있으면 미들웨어 스킵
        if request.META.get('HTTP_AUTHORIZATION'):
            return self.get_response(request)

        php_session_id = request.COOKIES.get('PHPSESSID')
        if not php_session_id:
            return self.get_response(request)

        try:
            member = self._resolve_member(php_session_id, request)
            if member:
                # JWT 생성
                refresh = RefreshToken.for_user(member)
                # request에 JWT 설정
                request.META['HTTP_AUTHORIZATION'] = f'Bearer {refresh.access_token}'
                request._bridge_jwt = {
                    'access': str(refresh.access_token),
                    'refresh': str(refresh),
                }
                # 로그 기록
                logger.info(
                    'SessionBridge: PHP user %s (PK=%d) mapped to JWT',
                    member.username,
                    member.pk,
                    extra={'correlation_id': getattr(request, 'correlation_id', '-')},
                )
        except Exception as e:
            logger.exception(
                'SessionBridge failed for PHPSESSID=%s: %s',
                php_session_id[:8] + '...' if php_session_id else 'None',
                str(e),
                extra={'correlation_id': getattr(request, 'correlation_id', '-')},
            )

        response = self.get_response(request)

        # 응답에 JWT 포함 (클라이언트가 이후 직접 사용)
        if hasattr(request, '_bridge_jwt'):
            response['X-Bridge-Token'] = request._bridge_jwt['access']
            response['X-Bridge-Refresh'] = request._bridge_jwt['refresh']

        return response

    def _resolve_member(self, php_session_id, request):
        """PHPSESSID -> Django Member 매핑 (캐시 우선)"""
        from apps.accounts.models import Member

        cache_key = f'{BRIDGE_CACHE_PREFIX}{php_session_id}'

        # 캐시 확인
        cached = cache.get(cache_key)
        if cached:
            try:
                member = Member.objects.get(pk=cached['member_pk'], is_deleted=False)
                logger.debug(
                    'SessionBridge: cache HIT for PHPSESSID',
                    extra={'correlation_id': getattr(request, 'correlation_id', '-')},
                )
                return member
            except Member.DoesNotExist:
                cache.delete(cache_key)

        # MySQL legacy DB 조회
        member_info = self._query_php_session(php_session_id)
        if not member_info:
            logger.warning(
                'SessionBridge: PHP session not found in legacy DB',
                extra={'correlation_id': getattr(request, 'correlation_id', '-')},
            )
            return None

        # Django Member 매핑
        try:
            member = Member.objects.get(
                username=member_info['id_member'],
                is_deleted=False,
            )
        except Member.DoesNotExist:
            logger.warning(
                'SessionBridge: no Django member for PHP user %s',
                member_info['id_member'],
                extra={'correlation_id': getattr(request, 'correlation_id', '-')},
            )
            return None

        # 캐시 저장
        cache.set(cache_key, {'member_pk': member.pk}, BRIDGE_CACHE_TTL)
        logger.debug(
            'SessionBridge: new mapping cached for PHPSESSID',
            extra={'correlation_id': getattr(request, 'correlation_id', '-')},
        )
        return member

    @staticmethod
    def _query_php_session(php_session_id):
        """
        MySQL legacy DB에서 PHP 세션 데이터 조회.

        PHP 세션 저장 방식에 따라 구현이 달라진다:
        - 파일 기반: /tmp/sess_{PHPSESSID} 파일 파싱
        - MySQL 기반: sessions 테이블 조회
        - Redis 기반: Redis에서 직접 조회

        실제 구현 전 PHP 세션 저장소 확인이 필수이다.
        """
        from django.db import connections

        try:
            with connections['legacy'].cursor() as cursor:
                # MySQL 세션 저장소 기준 쿼리
                # TODO: 실제 PHP 세션 저장소에 맞춰 쿼리 조정 필요
                cursor.execute("""
                    SELECT m.NO_MEMB, m.ID_MEMB, m.NM_MEMB, m.EMAIL
                    FROM TBL_SESSION s
                    JOIN TBL_MEMB m ON s.NO_MEMB = m.NO_MEMB
                    WHERE s.SESSION_ID = %s
                      AND s.EXPIRE_AT > NOW()
                      AND m.DL_GB = 'N'
                    LIMIT 1
                """, [php_session_id])

                row = cursor.fetchone()
                if row:
                    return {
                        'no_memb': row[0],
                        'id_member': row[1],  # username
                        'nm_memb': row[2],
                        'email': row[3],
                    }
        except Exception as e:
            logger.exception('Failed to query PHP session: %s', str(e))

        return None
