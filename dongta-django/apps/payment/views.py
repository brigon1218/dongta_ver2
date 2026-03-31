import uuid
import logging
import hmac
import hashlib
from rest_framework import generics, permissions, status
from django.conf import settings
from django.utils import timezone
from django.db import transaction
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from core.utils import success_response, error_response
from .models import PointAccount, PaymentHistory, PaymentStatus
from .serializers import (
    PointAccountSerializer,
    PaymentHistorySerializer,
    PointUseSerializer,
    PointChargeSerializer,
    DanalReadySerializer,
    DanalCallbackSerializer,
)
from .danal.client import DanalClient
from .tasks import sync_payment_to_mysql
from .services import PaymentService

logger = logging.getLogger(__name__)


class BalanceView(generics.GenericAPIView):
    """
    GET /api/v1/payment/balance/ — 포인트 잔액 조회 (인증 필요)
    캐시: 30초 (사용자별로 캐싱)
    """
    permission_classes = [permissions.IsAuthenticated]

    @ratelimit(key='user', rate='30/m', method='GET', block=False)
    def get(self, request):
        point_account, _ = PointAccount.objects.get_or_create(member=request.user)
        serializer = PointAccountSerializer(point_account)
        return success_response(serializer.data)


class PaymentHistoryListView(generics.GenericAPIView):
    """
    GET /api/v1/payment/history/ — 결제 내역 조회 (인증 필요)
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        queryset = PaymentHistory.objects.filter(
            member=request.user,
            is_deleted=False
        ).order_by('-created_at')

        # 필터: 성공 여부
        is_success = request.query_params.get('is_success')
        if is_success is not None:
            queryset = queryset.filter(is_success=(is_success.lower() == 'true'))

        # 페이지네이션
        page = int(request.query_params.get('page', 1))
        limit = int(request.query_params.get('limit', 20))
        total = queryset.count()
        offset = (page - 1) * limit
        histories = queryset[offset:offset + limit]

        serializer = PaymentHistorySerializer(histories, many=True)
        return success_response(
            serializer.data,
            meta={'page': page, 'total': total, 'limit': limit}
        )


class PointUseView(generics.GenericAPIView):
    """
    POST /api/v1/payment/use/ — 포인트 차감 (인증 필요)
    Request body: {"amount": 1000}
    Rate limit: 20 requests per minute per user
    """
    permission_classes = [permissions.IsAuthenticated]

    @ratelimit(key='user', rate='20/m', method='POST', block=True)
    def post(self, request):
        serializer = PointUseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        description = serializer.validated_data.get('description', '서비스 사용')

        try:
            point_account = PaymentService.use_points(request.user, amount, description)
            return success_response({
                'message': f'{amount} 포인트가 차감되었습니다.',
                'used_amount': amount,
                'remaining_balance': point_account.balance,
            })
        except ValueError as e:
            return error_response(
                'PAY_001',
                str(e),
                http_status=status.HTTP_400_BAD_REQUEST
            )


class PointChargeView(generics.GenericAPIView):
    """
    POST /api/v1/payment/charge/ — 포인트 충전 요청 (인증 필요)
    다날 결제를 통한 포인트 충전 요청을 생성합니다.
    Rate limit: 5 requests per minute per user
    """
    permission_classes = [permissions.IsAuthenticated]

    @ratelimit(key='user', rate='5/m', method='POST', block=True)
    def post(self, request):
        serializer = PointChargeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        pay_method = serializer.validated_data['pay_method']

        # 주문 ID 생성 (UUID 기반)
        order_id = f'DONGTA-{uuid.uuid4().hex[:16].upper()}'

        # 결제 내역 사전 생성 (대기 상태)
        payment = PaymentHistory.objects.create(
            member=request.user,
            amount=amount,
            point_amount=amount,  # 1원 = 1포인트
            pay_method=pay_method,
            status=PaymentStatus.PENDING,
            danal_order_id=order_id,
        )

        # 다날 결제 URL 구성
        danal_merchant_id = getattr(settings, 'DANAL_MERCHANT_ID', '')
        return_url = getattr(settings, 'DANAL_RETURN_URL', '')

        return success_response({
            'order_id': order_id,
            'amount': amount,
            'pay_method': pay_method,
            'payment_id': payment.id,
            'danal_merchant_id': danal_merchant_id,
            'return_url': return_url,
            'message': '결제 준비가 완료되었습니다. 다날 결제 창을 통해 결제를 진행하세요.',
        }, http_status=status.HTTP_201_CREATED)


class DanalReadyView(generics.GenericAPIView):
    """
    POST /api/v1/payment/danal/ready/ — 다날 결제 준비 (인증 필요)
    다날 PG 결제 세션을 초기화하고 결제 URL(STARTURL)을 반환합니다.
    Rate limit: 10 requests per minute per user
    """
    permission_classes = [permissions.IsAuthenticated]

    @ratelimit(key='user', rate='10/m', method='POST', block=True)
    def post(self, request):
        serializer = DanalReadySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        amount = serializer.validated_data['amount']
        pay_method = serializer.validated_data['pay_method']
        order_id = f'DONGTA-{uuid.uuid4().hex[:16].upper()}'

        try:
            payment, response = PaymentService.initiate_danal_payment(
                member=request.user,
                amount=amount,
                pay_method=pay_method,
                order_id=order_id
            )

            if response.is_success:
                return success_response({
                    'order_id': order_id,
                    'payment_id': payment.id,
                    'tid': payment.tid,
                    'amount': amount,
                    'start_url': response.get('STARTURL'),
                    'message': '결제 준비가 완료되었습니다. 다날 결제 창으로 이동하세요.',
                }, http_status=status.HTTP_201_CREATED)
            else:
                return error_response(
                    'PAY_002',
                    f'다날 서버 통신 실패: {response.return_msg}',
                    http_status=status.HTTP_400_BAD_REQUEST
                )
        except ValueError as e:
            return error_response('PAY_003', str(e), http_status=status.HTTP_400_BAD_REQUEST)


class DanalCallbackView(generics.GenericAPIView):
    """
    POST /api/v1/payment/danal/callback/ — 다날 결제 결과 수신 및 승인 (서버-서버)
    다날 서버에서 전송하는 결제 결과를 수신하고, HMAC 서명을 검증한 후 최종 승인을 처리합니다.
    """
    permission_classes = [permissions.AllowAny]

    # Danal 서버 IP 범위 (실제 운영 환경에서는 다날에서 제공하는 최신 IP 사용)
    DANAL_IP_WHITELIST = [
        '211.115.10.0/24',      # Danal 송금용 IP 대역 (예시)
        '182.31.0.0/16',        # Danal 결제 서버 대역 (예시)
        '127.0.0.1',            # 로컬 테스트
    ]

    def _is_ip_whitelisted(self, client_ip: str) -> bool:
        """
        클라이언트 IP가 화이트리스트에 포함되어 있는지 확인합니다.

        Args:
            client_ip: 클라이언트 IP 주소

        Returns:
            bool: IP가 화이트리스트에 포함된 경우 True
        """
        try:
            import ipaddress
            client_ip_obj = ipaddress.ip_address(client_ip)
            for whitelisted_range in self.DANAL_IP_WHITELIST:
                if client_ip_obj in ipaddress.ip_network(whitelisted_range):
                    return True
            return False
        except ValueError as e:
            logger.error(f"Invalid IP address format: {client_ip}, error: {e}")
            return False

    def _verify_hmac_signature(self, request_data: dict, signature: str) -> bool:
        """
        다날 서버 응답의 HMAC-SHA256 서명을 검증합니다.
        Danal의 공개 키 또는 시크릿을 사용하여 필요에 따라 구현합니다.

        Args:
            request_data: 다날 콜백 요청 데이터
            signature: 다날에서 전송한 서명값 (헤더 또는 파라미터)

        Returns:
            bool: 서명이 유효한 경우 True, 위조/변조된 경우 False
        """
        # 현재 구현: 다날 공개 문서 기준
        # 실제 운영 시 다날에서 제공하는 HMAC 검증 방식 확인 필요
        try:
            # 검증 필드 정렬 (다날 기준)
            verify_fields = [
                request_data.get('RETURNCODE', ''),
                request_data.get('RETURNMSG', ''),
                request_data.get('TID', ''),
                request_data.get('ORDERID', ''),
            ]
            verify_string = '|'.join(verify_fields)

            # HMAC-SHA256 계산 (시크릿은 DANAL_MERCHANT_KEY)
            computed_hmac = hmac.new(
                settings.DANAL_MERCHANT_KEY.encode('utf-8'),
                verify_string.encode('utf-8'),
                hashlib.sha256
            ).hexdigest()

            return computed_hmac == signature
        except Exception as e:
            logger.error(f"HMAC verification error: {e}")
            return False

    def post(self, request):
        # IP 화이트리스트 검증 (보안 필수)
        client_ip = request.META.get('REMOTE_ADDR', '')
        if not self._is_ip_whitelisted(client_ip):
            logger.warning(f"Unauthorized IP callback attempt from {client_ip}")
            return error_response('PAY_005', '콜백 검증에 실패했습니다. (IP 주소 검증 오류)', http_status=status.HTTP_403_FORBIDDEN)

        tid = request.data.get('TID')
        order_id = request.data.get('ORDERID')

        if not tid or not order_id:
            return error_response('PAY_003', '유효하지 않은 결제 결과입니다.')

        # HMAC 서명 검증 (보안 필수 - 무조건 검증)
        signature = request.data.get('HMAC', request.headers.get('X-Danal-Hmac'))
        if not signature:
            logger.warning(f"HMAC signature missing for order {order_id}")
            return error_response('PAY_005', '콜백 검증에 실패했습니다. (서명 누락)', http_status=status.HTTP_403_FORBIDDEN)

        if not self._verify_hmac_signature(request.data, signature):
            logger.warning(f"HMAC verification failed for order {order_id}")
            return error_response('PAY_005', '콜백 검증에 실패했습니다. (서명 검증 오류)', http_status=status.HTTP_403_FORBIDDEN)

        try:
            payment = PaymentHistory.objects.get(danal_order_id=order_id, tid=tid)
        except PaymentHistory.DoesNotExist:
            return error_response('PAY_002', '해당 주문을 찾을 수 없습니다.')

        if payment.status == PaymentStatus.APPROVED:
            return success_response({'message': '이미 승인된 결제입니다.', 'order_id': order_id})

        # PaymentService를 통해 결제 승인
        response = PaymentService.approve_danal_payment(payment)

        if response.is_success:
            return success_response({
                'message': f'{payment.point_amount} 포인트가 충전되었습니다.',
                'order_id': order_id,
                'point_amount': payment.point_amount,
            })
        else:
            return error_response(
                'PAY_002',
                f'결제 승인 실패: {response.return_msg}',
                http_status=status.HTTP_400_BAD_REQUEST
            )


class DanalCancelView(generics.GenericAPIView):
    """
    POST /api/v1/payment/danal/cancel/ — 다날 결제 취소 (인증 필요)
    Rate limit: 10 requests per minute per user
    """
    permission_classes = [permissions.IsAuthenticated]

    @ratelimit(key='user', rate='10/m', method='POST', block=True)
    def post(self, request):
        payment_id = request.data.get('payment_id')
        reason = request.data.get('reason', '사용자 요청 취소')

        try:
            payment = PaymentHistory.objects.get(
                id=payment_id,
                member=request.user,
                status=PaymentStatus.APPROVED
            )
        except PaymentHistory.DoesNotExist:
            return error_response('PAY_002', '취소 가능한 결제 내역을 찾을 수 없습니다.')

        try:
            response = PaymentService.cancel_danal_payment(payment, reason)

            if response.is_success:
                return success_response({'message': '결제가 취소되었습니다.'})
            else:
                return error_response('PAY_002', f'취소 실패: {response.return_msg}')
        except ValueError as e:
            return error_response('PAY_001', str(e))
