from rest_framework import generics, permissions, status, views
from django.db import transaction
from django.utils import timezone
from django_ratelimit.decorators import ratelimit
from django.utils.decorators import method_decorator
from core.utils import success_response, error_response
from apps.accounts.models import Member
from apps.payment.models import PaymentHistory, PointAccount
from apps.board.models import Post, Comment
from apps.business114.models import Business
from apps.recruit.models import JobNotice
from apps.payment.serializers import PaymentHistorySerializer
from .serializers import (
    UserProfileSerializer,
    PasswordChangeSerializer,
    WithdrawalSerializer,
    ActivitySummarySerializer
)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    GET/PATCH /api/v1/mypage/profile/ — 내 상세 프로필 조회 및 수정
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user

    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return success_response(serializer.data)

    def patch(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success_response(serializer.data)


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class PasswordChangeView(views.APIView):
    """
    POST /api/v1/mypage/password/ — 비밀번호 변경 (Rate Limit: 5회/분, IP 기준)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        # 현재 비밀번호 확인
        if not user.check_password(serializer.validated_data['old_password']):
            return error_response('AUTH_002', '현재 비밀번호가 일치하지 않습니다.', status=status.HTTP_400_BAD_REQUEST)

        # 비밀번호 변경
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return success_response({'message': '비밀번호가 성공적으로 변경되었습니다.'})


@method_decorator(ratelimit(key='ip', rate='5/m', method='POST', block=True), name='post')
class WithdrawalView(views.APIView):
    """
    POST /api/v1/mypage/withdraw/ — 회원 탈퇴 (소프트 삭제, Rate Limit: 5회/분, IP 기준)
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = WithdrawalSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = request.user

        # 비밀번호 확인
        if not user.check_password(serializer.validated_data['password']):
            return error_response('AUTH_002', '비밀번호가 일치하지 않습니다.', status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # 소프트 삭제 처리
            user.soft_delete()
            user.is_active = False
            user.want_quit = True
            user.quit_reason = serializer.validated_data.get('reason', '')
            user.save(update_fields=['is_active', 'want_quit', 'quit_reason'])

        return success_response({'message': '회원 탈퇴가 완료되었습니다. 그동안 이용해 주셔서 감사합니다.'})


class PointHistoryView(generics.ListAPIView):
    """
    GET /api/v1/mypage/points/ — 내 포인트 충전 내역 조회
    """
    serializer_class = PaymentHistorySerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return PaymentHistory.objects.filter(member=self.request.user, is_deleted=False).order_by('-created_at')

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # 포인트 잔액 정보 포함
        point_account, _ = PointAccount.objects.get_or_create(member=request.user)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                'balance': point_account.balance,
                'history': serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return success_response({
            'balance': point_account.balance,
            'history': serializer.data
        })


class ActivitySummaryView(views.APIView):
    """
    GET /api/v1/mypage/summary/ — 내 활동 요약 정보 집계
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        user = request.user
        
        data = {
            'posts_count': Post.objects.filter(member=user, is_deleted=False).count(),
            'comments_count': Comment.objects.filter(member=user, is_deleted=False).count(),
            'businesses_count': Business.objects.filter(member=user, is_deleted=False).count(),
            'job_notices_count': JobNotice.objects.filter(member=user, is_deleted=False).count(),
        }
        
        serializer = ActivitySummarySerializer(data)
        return success_response(serializer.data)
