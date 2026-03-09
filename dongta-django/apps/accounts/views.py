from rest_framework import generics, permissions, status
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from core.utils import success_response, error_response
from .models import Member
from .serializers import RegisterSerializer, MemberSerializer, PasswordChangeSerializer


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
