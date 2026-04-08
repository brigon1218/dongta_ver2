"""
관리자 전용 REST API 뷰 (Design S4.6)
- POST /api/v1/admin/notices/:id/approve/
- POST /api/v1/admin/business/:id/approve/
- GET  /api/v1/admin/members/
- POST /api/v1/admin/payment/confirm/
"""
import logging
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from core.utils import success_response, error_response

logger = logging.getLogger(__name__)


class IsAdminUser(permissions.BasePermission):
    """슈퍼유저 또는 스태프만 허용"""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and
                    (request.user.is_staff or request.user.is_superuser))


class AdminNoticeApproveView(generics.GenericAPIView):
    """
    POST /api/v1/admin/notices/:id/approve/
    채용공고 승인/반려 (관리자 전용)
    Body: {"approve": true|false, "reason": "optional"}
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        from apps.recruit.models import JobNotice
        try:
            notice = JobNotice.objects.get(pk=pk, is_deleted=False)
        except JobNotice.DoesNotExist:
            return error_response('NOT_FOUND', '채용공고를 찾을 수 없습니다.',
                                  http_status=status.HTTP_404_NOT_FOUND)

        approve = request.data.get('approve', True)
        notice.is_approved = bool(approve)
        notice.save(update_fields=['is_approved'])

        action = '승인' if approve else '반려'
        logger.info(f"Admin {request.user.username} {action} notice #{pk}")
        return success_response({
            'id': notice.id,
            'is_approved': notice.is_approved,
            'message': f'채용공고가 {action}되었습니다.',
        })


class AdminBusinessApproveView(generics.GenericAPIView):
    """
    POST /api/v1/admin/business/:id/approve/
    업체 승인/반려 (관리자 전용)
    Body: {"approve": true|false}
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        from apps.business114.models import Business
        try:
            business = Business.objects.get(pk=pk, is_deleted=False)
        except Business.DoesNotExist:
            return error_response('NOT_FOUND', '업체를 찾을 수 없습니다.',
                                  http_status=status.HTTP_404_NOT_FOUND)

        approve = request.data.get('approve', True)
        business.is_approved = bool(approve)
        business.save(update_fields=['is_approved'])

        action = '승인' if approve else '반려'
        logger.info(f"Admin {request.user.username} {action} business #{pk}")
        return success_response({
            'id': business.id,
            'is_approved': business.is_approved,
            'message': f'업체가 {action}되었습니다.',
        })


class AdminMemberListView(generics.GenericAPIView):
    """
    GET /api/v1/admin/members/
    회원 목록 조회 (관리자 전용)
    Query params: page, page_size, q (검색), is_active, region
    """
    permission_classes = [IsAdminUser]

    def get(self, request):
        from apps.accounts.models import Member
        from apps.accounts.serializers import MemberSerializer

        queryset = Member.objects.filter(is_deleted=False).order_by('-created_at')

        # 검색
        q = request.query_params.get('q')
        if q:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(username__icontains=q) |
                Q(name__icontains=q) |
                Q(email__icontains=q) |
                Q(phone__icontains=q)
            )

        # 필터
        is_active = request.query_params.get('is_active')
        if is_active is not None:
            queryset = queryset.filter(is_active=(is_active.lower() == 'true'))

        region = request.query_params.get('region')
        if region:
            queryset = queryset.filter(region=region)

        # 페이지네이션
        page = max(1, int(request.query_params.get('page', 1)))
        page_size = min(100, max(1, int(request.query_params.get('page_size', 20))))
        total = queryset.count()
        offset = (page - 1) * page_size
        members = queryset[offset:offset + page_size]

        serializer = MemberSerializer(members, many=True)
        return success_response(
            serializer.data,
            meta={'page': page, 'total': total, 'page_size': page_size,
                  'total_pages': (total + page_size - 1) // page_size}
        )


class AdminPaymentConfirmView(generics.GenericAPIView):
    """
    POST /api/v1/admin/payment/confirm/
    무통장 결제 수동 확인 (관리자 전용)
    Body: {"payment_id": 123, "memo": "optional"}
    """
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.payment.models import PaymentHistory, PaymentStatus, PointAccount
        from django.db import transaction

        payment_id = request.data.get('payment_id')
        if not payment_id:
            return error_response('VALID_001', 'payment_id는 필수입니다.',
                                  http_status=status.HTTP_400_BAD_REQUEST)

        try:
            payment = PaymentHistory.objects.get(
                id=payment_id,
                pay_method='bank',
                is_deleted=False,
            )
        except PaymentHistory.DoesNotExist:
            return error_response('NOT_FOUND', '무통장 결제 내역을 찾을 수 없습니다.',
                                  http_status=status.HTTP_404_NOT_FOUND)

        if payment.status == PaymentStatus.APPROVED:
            return error_response('PAY_DUP', '이미 승인된 결제입니다.',
                                  http_status=status.HTTP_409_CONFLICT)

        with transaction.atomic():
            payment = PaymentHistory.objects.select_for_update().get(pk=payment.pk)
            payment.status = PaymentStatus.APPROVED
            payment.is_success = True
            payment.save(update_fields=['status', 'is_success'])

            point_account, _ = PointAccount.objects.get_or_create(member=payment.member)
            point_account.total_charged += payment.point_amount
            point_account.save(update_fields=['total_charged'])

        logger.info(
            f"Admin {request.user.username} confirmed bank payment #{payment_id} "
            f"({payment.point_amount}pts for {payment.member.username})"
        )
        return success_response({
            'payment_id': payment.id,
            'member': payment.member.username,
            'point_amount': payment.point_amount,
            'new_balance': point_account.balance,
            'message': f'{payment.point_amount} 포인트가 지급되었습니다.',
        })
