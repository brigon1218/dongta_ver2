from rest_framework import generics, permissions, status
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from core.utils import success_response, error_response
from .models import Member, PasswordResetToken
from .serializers import (
    RegisterSerializer, MemberSerializer, PasswordChangeSerializer,
    PasswordResetRequestSerializer, PasswordResetConfirmSerializer,
    SocialLoginSerializer
)
from .tasks import send_password_reset_email
import requests
import json


class RegisterView(generics.CreateAPIView):
    """POST /api/v1/auth/register/ — 회원가입"""
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        member = serializer.save()
        return success_response(
            MemberSerializer(member).data,
            http_status=status.HTTP_201_CREATED
        )


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class LoginView(generics.GenericAPIView):
    """POST /api/v1/auth/login/ — 로그인 (JWT 발급), Rate Limit: 5회/분 (IP 기준)"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        username = request.data.get('username', '').strip()
        password = request.data.get('password', '')

        if not username or not password:
            return error_response('VALID_001', '아이디와 비밀번호를 입력해주세요.')

        try:
            member = Member.objects.get(username=username, is_deleted=False)
        except Member.DoesNotExist:
            return error_response('AUTH_002', '아이디 또는 비밀번호가 올바르지 않습니다.',
                                  http_status=status.HTTP_401_UNAUTHORIZED)

        if not member.check_password(password):
            return error_response('AUTH_002', '아이디 또는 비밀번호가 올바르지 않습니다.',
                                  http_status=status.HTTP_401_UNAUTHORIZED)

        if not member.is_active:
            return error_response('AUTH_004', '비활성화된 계정입니다.',
                                  http_status=status.HTTP_401_UNAUTHORIZED)

        # 로그인 정보 업데이트
        member.last_login_at = timezone.now()
        member.login_count += 1
        member.save(update_fields=['last_login_at', 'login_count'])

        refresh = RefreshToken.for_user(member)
        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': MemberSerializer(member).data,
        })


class LogoutView(generics.GenericAPIView):
    """POST /api/v1/auth/logout/ — 로그아웃 (토큰 블랙리스트)"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        try:
            refresh_token = request.data.get('refresh')
            token = RefreshToken(refresh_token)
            token.blacklist()
            return success_response({'message': '로그아웃되었습니다.'})
        except Exception:
            return error_response('AUTH_005', '유효하지 않은 토큰입니다.')


class MeView(generics.RetrieveUpdateAPIView):
    """GET/PUT /api/v1/auth/me/ — 내 정보 조회/수정"""
    serializer_class = MemberSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def retrieve(self, request, *args, **kwargs):
        return success_response(self.get_serializer(self.get_object()).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', True)
        serializer = self.get_serializer(
            self.get_object(), data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success_response(serializer.data)


class PasswordChangeView(generics.GenericAPIView):
    """POST /api/v1/auth/password/change/ — 비밀번호 변경"""
    serializer_class = PasswordChangeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = self.get_serializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        request.user.set_password(serializer.validated_data['new_password'])
        request.user.save()
        return success_response({'message': '비밀번호가 변경되었습니다.'})


class PasswordResetRequestView(generics.GenericAPIView):
    """POST /api/v1/auth/password/reset/ — 비밀번호 재설정 이메일 발송"""
    serializer_class = PasswordResetRequestSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data['email']
        member = Member.objects.get(email=email, is_deleted=False)

        # 기존 미사용 토큰 만료 처리
        PasswordResetToken.objects.filter(
            member=member,
            is_used=False
        ).delete()

        # 새 토큰 생성
        reset_token = PasswordResetToken.create_token(member)

        # 이메일 발송 (비동기)
        send_password_reset_email.delay(
            member_id=member.id,
            email=email,
            token=reset_token.token
        )

        return success_response(
            {'message': '비밀번호 재설정 이메일을 발송했습니다. 이메일을 확인해주세요.'}
        )


class PasswordResetConfirmView(generics.GenericAPIView):
    """POST /api/v1/auth/password/reset/confirm/ — 비밀번호 재설정 확인"""
    serializer_class = PasswordResetConfirmSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        reset_token = serializer.validated_data['reset_token']
        new_password = serializer.validated_data['new_password']

        # 비밀번호 변경
        member = reset_token.member
        member.set_password(new_password)
        member.save()

        # 토큰 사용 표시
        reset_token.mark_used()

        return success_response(
            {'message': '비밀번호가 재설정되었습니다.'}
        )


class SocialLoginView(generics.GenericAPIView):
    """POST /api/v1/auth/social/login/ — 소셜 로그인"""
    serializer_class = SocialLoginSerializer
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        provider = serializer.validated_data['provider']
        access_token = serializer.validated_data['access_token']

        # 소셜 제공자별 사용자 정보 조회
        if provider == 'google':
            user_info = self._get_google_user_info(access_token)
            if not user_info:
                return error_response(
                    'AUTH_SOCIAL_001',
                    '구글 인증에 실패했습니다.',
                    http_status=status.HTTP_401_UNAUTHORIZED
                )
            provider_id = user_info.get('sub')
            email = user_info.get('email')
            name = user_info.get('name', '')

        elif provider == 'naver':
            user_info = self._get_naver_user_info(access_token)
            if not user_info:
                return error_response(
                    'AUTH_SOCIAL_002',
                    '네이버 인증에 실패했습니다.',
                    http_status=status.HTTP_401_UNAUTHORIZED
                )
            provider_id = user_info.get('id')
            email = user_info.get('email')
            name = user_info.get('name', '')

        else:
            return error_response(
                'AUTH_SOCIAL_003',
                '지원하지 않는 소셜 로그인입니다.',
                http_status=status.HTTP_400_BAD_REQUEST
            )

        # 기존 회원 조회
        member = None
        if provider == 'google':
            member = Member.objects.filter(
                google_id=provider_id,
                is_deleted=False
            ).first()
        elif provider == 'naver':
            member = Member.objects.filter(
                naver_id=provider_id,
                is_deleted=False
            ).first()

        # 신규 회원가입
        if not member:
            import uuid
            username = f"{provider}_{provider_id}"[:50]
            # 중복 방지
            counter = 1
            original_username = username
            while Member.objects.filter(username=username).exists():
                username = f"{original_username}_{counter}"[:50]
                counter += 1

            member = Member.objects.create_user(
                username=username,
                email=email or f"no-email-{provider_id}@dongta.local",
                password=str(uuid.uuid4()),  # 사용하지 않음
                name=name
            )

            if provider == 'google':
                member.google_id = provider_id
            elif provider == 'naver':
                member.naver_id = provider_id
            member.save()

        # JWT 토큰 발급
        refresh = RefreshToken.for_user(member)
        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': MemberSerializer(member).data,
        })

    @staticmethod
    def _get_google_user_info(access_token):
        """구글 access_token으로 사용자 정보 조회"""
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=5
            )
            if response.status_code == 200:
                return response.json()
        except Exception:
            pass
        return None

    @staticmethod
    def _get_naver_user_info(access_token):
        """네이버 access_token으로 사용자 정보 조회"""
        try:
            response = requests.get(
                'https://openapi.naver.com/v1/nid/me',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=5
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('response')
        except Exception:
            pass
        return None


# =====================================================================
# Phase 2.1: PHP ↔ Django 하이브리드 연동
# =====================================================================

class BridgeAuthView(generics.GenericAPIView):
    """
    POST /api/v1/auth/bridge/
    PHP 세션 쿠키 -> Django JWT 명시적 발급

    SessionBridgeMiddleware는 자동 처리를 담당하고,
    이 View는 클라이언트가 명시적으로 JWT를 요청할 때 사용한다.
    """
    permission_classes = [permissions.AllowAny]
    throttle_scope = 'bridge'

    def post(self, request):
        from apps.accounts.middleware import SessionBridgeMiddleware
        from django.core.cache import cache

        php_session_id = (
            request.data.get('php_session_id')
            or request.COOKIES.get('PHPSESSID')
        )

        if not php_session_id:
            return error_response(
                'BRIDGE_001',
                'PHP 세션이 유효하지 않습니다',
                details={
                    'session_id_present': False,
                    'hint': 'Cookie에 PHPSESSID가 포함되어 있는지 확인하세요'
                },
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # PHP 세션 -> 회원 정보 조회
        member_info = SessionBridgeMiddleware._query_php_session(php_session_id)
        if not member_info:
            return error_response(
                'BRIDGE_002',
                '세션에 해당하는 회원을 찾을 수 없습니다',
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # Django Member 매핑
        try:
            member = Member.objects.get(
                username=member_info['id_member'],
                is_deleted=False,
            )
        except Member.DoesNotExist:
            return error_response(
                'BRIDGE_003',
                'Django 회원 매핑에 실패했습니다',
                details={'php_username': member_info['id_member']},
                http_status=status.HTTP_401_UNAUTHORIZED,
            )

        # JWT 발급
        refresh = RefreshToken.for_user(member)

        # 패스워드 업그레이드 필요 여부 확인
        password_upgrade_needed = (
            member.password.startswith('md5$')
            if member.password else False
        )

        # 브리지 성공 통계 기록
        cache_key = f'bridge:success:{timezone.now().strftime("%Y-%m-%d")}'
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, 86400)  # 24시간

        return success_response({
            'access': str(refresh.access_token),
            'refresh': str(refresh),
            'user': MemberSerializer(member).data,
            'bridge_info': {
                'php_session_valid': True,
                'password_upgrade_needed': password_upgrade_needed,
            },
        })


class BridgeRevokeView(generics.GenericAPIView):
    """
    POST /api/v1/auth/bridge/revoke/
    JWT 토큰 무효화 (Redis 블랙리스트)

    PHP 로그아웃 시 Django JWT도 함께 무효화하기 위해 사용.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from django.core.cache import cache

        token = request.data.get('token')
        if not token:
            return error_response(
                'BRIDGE_004',
                '토큰이 제공되지 않았습니다',
                http_status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # 토큰을 블랙리스트에 추가
            cache_key = f'bridge:revoked:{token[:20]}'
            cache.set(cache_key, True, 86400)  # 24시간 보관

            # 브리지 성공 통계 기록
            cache_key = f'bridge:revoke:{timezone.now().strftime("%Y-%m-%d")}'
            current_count = cache.get(cache_key, 0)
            cache.set(cache_key, current_count + 1, 86400)

            return success_response({'message': '토큰이 무효화되었습니다'})
        except Exception as e:
            return error_response(
                'BRIDGE_005',
                '토큰 무효화에 실패했습니다',
                details={'error': str(e)},
                http_status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
